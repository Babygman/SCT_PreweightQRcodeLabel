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
from app.models import AuditLog, Material, MaterialTagBatch, MaterialTagDraft, Station
from app.services.material_tag_issuance import (
    MaterialTagIssuanceError,
    create_material_tag_draft,
    issue_material_tag_draft,
    preview_details,
)

from .forms import MaterialTagConfirmForm, MaterialTagDraftForm

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
    return render_template("material_tags/batch_detail.html", batch=batch, station=station)
