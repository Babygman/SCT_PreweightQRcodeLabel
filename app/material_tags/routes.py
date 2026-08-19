from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagDraft,
    MaterialTagPrintEvent,
    Station,
    User,
)
from app.presentation import parse_user_date
from app.services.material_tag_issuance import (
    MaterialTagIssuanceError,
    create_material_tag_draft,
    create_print_event,
    issue_material_tag_draft,
    material_tag_qr_data_uri,
    preview_details,
)

from .forms import (
    MaterialTagConfirmForm,
    MaterialTagDraftForm,
    MaterialTagPrintForm,
    MaterialTagReprintForm,
)

bp = Blueprint("material_tags", __name__, url_prefix="/material-tags")


def feature_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config.get("MATERIAL_TAG_ISSUANCE_ENABLED", False):
            abort(404)
        return view(*args, **kwargs)

    return wrapped


def protected(view):
    return feature_required(
        login_required(station_required(roles_required("SUPERVISOR", "ADMIN")(view)))
    )


@bp.get("/")
@protected
def index():
    return redirect(url_for("material_tags.new"))


@bp.route("/new", methods=["GET", "POST"])
@protected
def new():
    form = MaterialTagDraftForm()
    if request.method == "GET" and request.args.get("material_id"):
        form.material_id.data = request.args.get("material_id")
    selected_material = None
    if form.material_id.data:
        try:
            selected_material = db.session.get(Material, int(form.material_id.data))
        except (TypeError, ValueError):
            selected_material = None
    if form.validate_on_submit():
        try:
            draft = create_material_tag_draft(
                values=form.data,
                user_id=current_user.id,
                station_id=session["station_id"],
                lifetime_minutes=current_app.config["MATERIAL_TAG_DRAFT_LIFETIME_MINUTES"],
            )
        except MaterialTagIssuanceError as exc:
            flash(str(exc), "danger")
        else:
            return redirect(url_for("material_tags.preview", token=draft.draft_token))
    return render_template("material_tags/new.html", form=form, selected_material=selected_material)


@bp.get("/materials/search")
@protected
def material_search():
    query = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    statement = select(Material).where(Material.is_active == True)  # noqa: E712
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                Material.code.ilike(pattern, escape="\\"), Material.name.ilike(pattern, escape="\\")
            )
        )
    statement = statement.order_by(Material.code, Material.id)
    pagination = db.paginate(
        statement,
        page=page,
        per_page=current_app.config["MATERIAL_TAG_SEARCH_PAGE_SIZE"],
        max_per_page=current_app.config["MATERIAL_TAG_SEARCH_PAGE_SIZE"],
        error_out=False,
    )
    return render_template(
        "material_tags/material_search.html",
        materials=pagination.items,
        pagination=pagination,
        query=query,
    )


def _owned_draft(token):
    draft = db.session.scalar(select(MaterialTagDraft).where(MaterialTagDraft.draft_token == token))
    if draft is None:
        abort(404)
    if draft.created_by_user_id != current_user.id:
        abort(403)
    return draft


@bp.get("/drafts/<token>/preview")
@protected
def preview(token):
    draft = _owned_draft(token)
    if draft.status == "ISSUED" and draft.issued_batch_id:
        return redirect(url_for("material_tags.batch_detail", batch_id=draft.issued_batch_id))
    try:
        details = preview_details(draft)
    except MaterialTagIssuanceError as exc:
        flash(str(exc), "danger")
        details = None
    return render_template(
        "material_tags/preview.html",
        draft=draft,
        details=details,
        confirm_form=MaterialTagConfirmForm(),
    )


@bp.post("/drafts/<token>/confirm")
@protected
def confirm(token):
    form = MaterialTagConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    _owned_draft(token)
    try:
        batch = issue_material_tag_draft(
            token=token, user_id=current_user.id, station_id=session["station_id"]
        )
    except MaterialTagIssuanceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("material_tags.preview", token=token))
    flash("Material Tags issued successfully.", "success")
    return redirect(url_for("material_tags.batch_detail", batch_id=batch.id))


@bp.get("/batches/<int:batch_id>")
@protected
def batch_detail(batch_id):
    return _render_batch_detail(batch_id)


def _render_batch_detail(
    batch_id, *, reprint_form=None, invalid_tag_id=None, status_code=200
):
    batch = db.get_or_404(MaterialTagBatch, batch_id)
    audit = db.session.scalar(
        select(AuditLog)
        .where(
            AuditLog.event_type == "MATERIAL_TAG_BATCH_ISSUED",
            AuditLog.entity_type == "MATERIAL_TAG_BATCH",
            AuditLog.entity_id == str(batch.id),
        )
        .order_by(AuditLog.occurred_at_utc.desc())
    )
    station = db.session.get(Station, audit.station_id) if audit and audit.station_id else None
    events = db.session.scalars(
        select(MaterialTagPrintEvent)
        .where(MaterialTagPrintEvent.batch_id == batch.id)
        .order_by(MaterialTagPrintEvent.requested_at_utc.desc(), MaterialTagPrintEvent.id.desc())
    ).all()
    original_exists = any(
        event.print_type == "ORIGINAL" and event.result == "RENDERED" for event in events
    )
    return (
        render_template(
            "material_tags/batch_detail.html",
            batch=batch,
            station=station,
            events=events,
            original_exists=original_exists,
            print_form=MaterialTagPrintForm(),
            reprint_form=reprint_form or MaterialTagReprintForm(),
            invalid_tag_id=invalid_tag_id,
        ),
        status_code,
    )


@bp.post("/batches/<int:batch_id>/print")
@protected
def print_batch(batch_id):
    form = MaterialTagPrintForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        event = create_print_event(
            batch_id=batch_id,
            user_id=current_user.id,
            station_id=session["station_id"],
            print_type="ORIGINAL",
        )
    except MaterialTagIssuanceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("material_tags.batch_detail", batch_id=batch_id))
    return redirect(url_for("material_tags.print_event_view", event_id=event.id))


@bp.post("/batches/<int:batch_id>/reprint")
@protected
def reprint_batch(batch_id):
    form = MaterialTagReprintForm()
    if not form.validate_on_submit():
        return _render_batch_detail(batch_id, reprint_form=form, status_code=400)
    try:
        event = create_print_event(
            batch_id=batch_id,
            user_id=current_user.id,
            station_id=session["station_id"],
            print_type="REPRINT",
            reason=form.reason.data,
        )
    except MaterialTagIssuanceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("material_tags.batch_detail", batch_id=batch_id))
    return redirect(url_for("material_tags.print_event_view", event_id=event.id))


@bp.post("/batches/<int:batch_id>/tags/<int:tag_id>/reprint")
@protected
def reprint_tag(batch_id, tag_id):
    batch = db.get_or_404(MaterialTagBatch, batch_id)
    tag = db.get_or_404(MaterialTag, tag_id)
    if tag.batch_id != batch.id:
        abort(404)
    form = MaterialTagReprintForm()
    if not form.validate_on_submit():
        return _render_batch_detail(
            batch_id,
            reprint_form=form,
            invalid_tag_id=tag_id,
            status_code=400,
        )
    try:
        event = create_print_event(
            batch_id=batch_id,
            tag_id=tag_id,
            user_id=current_user.id,
            station_id=session["station_id"],
            print_type="REPRINT",
            scope="INDIVIDUAL",
            reason=form.reason.data,
        )
    except MaterialTagIssuanceError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("material_tags.batch_detail", batch_id=batch_id))
    return redirect(url_for("material_tags.print_event_view", event_id=event.id))


@bp.get("/print-events/<int:event_id>/view")
@protected
def print_event_view(event_id):
    event = db.get_or_404(MaterialTagPrintEvent, event_id)
    tags = (
        [event.material_tag]
        if event.print_scope == "INDIVIDUAL" and event.material_tag is not None
        else sorted(event.batch.tags, key=lambda tag: tag.sequence_no)
    )
    return render_template(
        "material_tags/print.html",
        event=event,
        batch=event.batch,
        tags=tags,
        qr_data_uri=material_tag_qr_data_uri(event.batch.qr_payload),
    )


def _history_date(name):
    raw = request.args.get(name, "").strip()
    try:
        return parse_user_date(raw, required=False)
    except ValueError:
        abort(400)


@bp.get("/history")
@protected
def history():
    statement = select(MaterialTagBatch)
    partial_filters = {
        "batch_no": MaterialTagBatch.batch_no,
        "material_code": MaterialTagBatch.material_code_snapshot,
        "material_name": MaterialTagBatch.material_name_snapshot,
        "vendor_lot": MaterialTagBatch.vendor_lot,
        "purchase_order": MaterialTagBatch.purchase_order,
        "delivery_invoice": MaterialTagBatch.delivery_invoice,
    }
    for name, column in partial_filters.items():
        value = request.args.get(name, "").strip()
        if value:
            if len(value) > 200:
                abort(400)
            escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(column.ilike(f"%{escaped}%", escape="\\"))
    issued_by = request.args.get("issued_by", type=int)
    if issued_by:
        statement = statement.where(MaterialTagBatch.issued_by_user_id == issued_by)
    date_from, date_to = _history_date("date_from"), _history_date("date_to")
    if date_from and date_to and date_from > date_to:
        abort(400)
    if date_from:
        statement = statement.where(MaterialTagBatch.receiving_date >= date_from)
    if date_to:
        statement = statement.where(MaterialTagBatch.receiving_date <= date_to)
    statement = statement.order_by(
        MaterialTagBatch.issued_at_utc.desc(), MaterialTagBatch.id.desc()
    )
    page_size = current_app.config["MATERIAL_TAG_HISTORY_PAGE_SIZE"]
    pagination = db.paginate(
        statement,
        page=max(request.args.get("page", 1, type=int), 1),
        per_page=page_size,
        max_per_page=page_size,
        error_out=False,
    )
    users = db.session.scalars(select(User).order_by(User.username)).all()
    event_counts = {
        batch.id: {
            "original": any(
                e.print_type == "ORIGINAL" and e.result == "RENDERED" for e in batch.print_events
            ),
            "reprints": sum(e.print_type == "REPRINT" for e in batch.print_events),
        }
        for batch in pagination.items
    }
    return render_template(
        "material_tags/history.html",
        batches=pagination.items,
        pagination=pagination,
        users=users,
        event_counts=event_counts,
    )


@bp.get("/calibration")
@protected
def calibration():
    return render_template("material_tags/calibration.html")
