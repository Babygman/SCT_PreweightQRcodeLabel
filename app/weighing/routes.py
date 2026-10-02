import json
from io import BytesIO
from uuid import uuid4

import qrcode
from flask import (
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.i18n import message as ui_message
from app.models import ProductionOrder, Station, User, WeighingTransaction
from app.services.material_workflow import (
    build_material_queue,
    build_material_selection,
    save_material_queue_item,
)
from app.services.weighing import save_weighing, validate_material_tag
from app.services.workset import active_work_set_overview

from . import bp
from .forms import MaterialQueueWeightForm, ReweighForm, WeighingForm


def _completed_transaction_for_selected_station(transaction_id):
    transaction = db.get_or_404(WeighingTransaction, transaction_id)
    if (
        transaction.station_id != session["station_id"]
        or transaction.status not in ("COMPLETED", "CONSUMED")
        or not transaction.preweight_id
    ):
        abort(404)
    return transaction


def _current_transaction_for_selected_station(transaction_id):
    transaction = _completed_transaction_for_selected_station(transaction_id)
    if transaction.superseded_at_utc is not None:
        abort(409)
    return transaction


def _replacement_display_context(transactions):
    """Load display-only provenance for active replacement transactions."""
    replaced_ids = {
        transaction.replaces_transaction_id
        for transaction in transactions
        if transaction.replaces_transaction_id is not None
    }
    replaced = (
        db.session.scalars(
            select(WeighingTransaction).where(WeighingTransaction.id.in_(replaced_ids))
        ).all()
        if replaced_ids
        else []
    )
    user_ids = {
        transaction.weighed_by_user_id
        for transaction in transactions
        if transaction.replaces_transaction_id is not None
    }
    users = (
        db.session.scalars(select(User).where(User.id.in_(user_ids))).all()
        if user_ids
        else []
    )
    return (
        {transaction.id: transaction for transaction in replaced},
        {user.id: user for user in users},
    )


def _replacement_chain(transaction):
    """Follow only persisted replacement links; never infer historical links."""
    seen = set()
    current = transaction
    while current.replaces_transaction_id is not None:
        if current.id in seen:
            abort(409)
        seen.add(current.id)
        predecessor = db.session.get(
            WeighingTransaction, current.replaces_transaction_id
        )
        if predecessor is None:
            abort(409)
        current = predecessor

    chain = []
    while current is not None:
        if current.id in {entry.id for entry in chain}:
            abort(409)
        if (
            current.station_id != transaction.station_id
            or current.production_order_id != transaction.production_order_id
            or current.formula_item_id != transaction.formula_item_id
        ):
            abort(404)
        chain.append(current)
        current = (
            db.session.get(
                WeighingTransaction, current.superseded_by_transaction_id
            )
            if current.superseded_by_transaction_id is not None
            else None
        )
    return sorted(chain, key=lambda entry: (entry.weighed_at_utc, entry.id), reverse=True)


@bp.get("/order/<int:po_id>")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def order(po_id):
    production_order = db.get_or_404(ProductionOrder, po_id)
    if production_order.status != "READY" or production_order.formula is None:
        abort(403)
    transactions = db.session.scalars(
        select(WeighingTransaction).where(
            WeighingTransaction.production_order_id == production_order.id,
            WeighingTransaction.status.in_(("COMPLETED", "CONSUMED")),
            WeighingTransaction.superseded_at_utc.is_(None),
        )
    ).all()
    transactions_by_item = {
        transaction.formula_item_id: transaction for transaction in transactions
    }
    replaced_transactions_by_id, weighed_users_by_id = _replacement_display_context(
        transactions
    )
    return render_template(
        "weighing/order.html",
        order=production_order,
        form=WeighingForm(),
        transactions_by_item=transactions_by_item,
        replaced_transactions_by_id=replaced_transactions_by_id,
        weighed_users_by_id=weighed_users_by_id,
        reweigh_form=ReweighForm(),
    )


@bp.post("/order/<int:po_id>/line/<int:formula_item_id>")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def weigh_line(po_id, formula_item_id):
    form = WeighingForm()
    if form.validate_on_submit():
        result = save_weighing(
            po_id,
            formula_item_id,
            form.material_tag.data,
            form.actual_weight.data,
            current_user.id,
            session["station_id"],
        )
        flash(ui_message(result.message), "success" if result.success else "danger")
        if result.success:
            session["weighing_mode"] = "formula"
            return redirect(url_for("weighing.sticker", transaction_id=result.transaction.id))
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(ui_message(message), "danger")
    return redirect(url_for("weighing.order", po_id=po_id))


@bp.post("/order/<int:po_id>/line/<int:formula_item_id>/validate-material")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def validate_material(po_id, formula_item_id):
    payload = request.get_json(silent=True) or {}
    result = validate_material_tag(
        po_id, formula_item_id, payload.get("material_tag"), session["station_id"]
    )
    return jsonify(
        {
            "result": "MATCH" if result.success else "UN-MATCH",
            "code": result.code,
            "message": ui_message(result.message),
        }
    )


@bp.get("/transaction/<int:transaction_id>/sticker")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def sticker(transaction_id):
    transaction = _completed_transaction_for_selected_station(transaction_id)
    if not transaction.erp_qr_payload:
        abort(404)
    return render_template(
        "weighing/sticker.html",
        transaction=transaction,
        payload=json.loads(transaction.erp_qr_payload),
        weighed_by=db.session.get(User, transaction.weighed_by_user_id),
        weighing_station=db.session.get(Station, transaction.station_id),
        material_mode=session.get("weighing_mode") == "material",
        is_superseded=transaction.superseded_at_utc is not None,
        replacement_chain=db.session.scalars(
            select(WeighingTransaction)
            .where(
                WeighingTransaction.production_order_id
                == transaction.production_order_id,
                WeighingTransaction.formula_item_id == transaction.formula_item_id,
            )
            .order_by(WeighingTransaction.weighed_at_utc, WeighingTransaction.id)
        ).all(),
    )


@bp.get("/transaction/<int:transaction_id>/history")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def weighing_history(transaction_id):
    transaction = _completed_transaction_for_selected_station(transaction_id)
    chain = _replacement_chain(transaction)
    users = db.session.scalars(
        select(User).where(
            User.id.in_({entry.weighed_by_user_id for entry in chain})
        )
    ).all()
    stations = db.session.scalars(
        select(Station).where(Station.id.in_({entry.station_id for entry in chain}))
    ).all()
    return render_template(
        "weighing/history.html",
        chain=chain,
        production_order=db.session.get(
            ProductionOrder, transaction.production_order_id
        ),
        transactions_by_id={entry.id: entry for entry in chain},
        users_by_id={user.id: user for user in users},
        stations_by_id={station.id: station for station in stations},
        current_transaction=next(
            (entry for entry in chain if entry.superseded_at_utc is None), None
        ),
        reweigh_form=ReweighForm(),
    )


@bp.get("/transaction/<int:transaction_id>/qr.png")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def sticker_qr(transaction_id):
    transaction = _completed_transaction_for_selected_station(transaction_id)
    if not transaction.erp_qr_payload:
        abort(404)
    image = qrcode.make(transaction.erp_qr_payload)
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return send_file(stream, mimetype="image/png", max_age=0)


@bp.post("/transaction/<int:transaction_id>/reweigh")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def start_reweigh(transaction_id):
    transaction = _current_transaction_for_selected_station(transaction_id)
    form = ReweighForm()
    if not form.validate_on_submit():
        for messages in form.errors.values():
            for message in messages:
                flash(ui_message(message), "danger")
        return redirect(url_for("weighing.order", po_id=transaction.production_order_id))
    session["reweigh_original_transaction_id"] = transaction.id
    session["reweigh_reason"] = form.reason.data.strip()
    session["reweigh_workflow_attempt"] = uuid4().hex
    session["selected_material_code"] = transaction.material_code_snapshot
    session["active_material_tag"] = transaction.material_tag_raw_payload
    session["weighing_mode"] = "material"
    flash(ui_message("Reweigh started. Capture a new Tare before saving."), "success")
    return redirect(
        url_for("weighing.material_mode", material=transaction.material_code_snapshot)
    )


@bp.post("/reweigh/cancel")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def cancel_reweigh():
    session.pop("reweigh_original_transaction_id", None)
    session.pop("reweigh_reason", None)
    session.pop("reweigh_workflow_attempt", None)
    flash(ui_message("Reweigh cancelled. The original weighing remains current."), "success")
    return redirect(url_for("weighing.material_mode"))


@bp.get("/material")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def material_mode():
    overview = active_work_set_overview(session["station_id"])
    active_order_ids = [order.id for order in overview.orders]
    reweighed_material_context = {}
    if active_order_ids:
        active_replacements = db.session.scalars(
            select(WeighingTransaction)
            .where(
                    WeighingTransaction.production_order_id.in_(active_order_ids),
                    WeighingTransaction.superseded_at_utc.is_(None),
                    WeighingTransaction.replaces_transaction_id.is_not(None),
                )
            .order_by(WeighingTransaction.weighed_at_utc, WeighingTransaction.id)
        ).all()
        replaced_by_id, replacement_users_by_id = _replacement_display_context(
            active_replacements
        )
        for active_replacement in active_replacements:
            reweighed_material_context[active_replacement.material_code_snapshot] = {
                "transaction": active_replacement,
                "replaced": replaced_by_id[active_replacement.replaces_transaction_id],
                "user": replacement_users_by_id[active_replacement.weighed_by_user_id],
            }
    requested_material = request.args.get("material", type=str)
    if requested_material is not None:
        selection = build_material_selection(
            session["station_id"], requested_material.strip()
        )
        if not selection.success:
            abort(404)
        previous_material = session.get("selected_material_code")
        session["selected_material_code"] = selection.material.code
        if previous_material != selection.material.code:
            session.pop("active_material_tag", None)
    else:
        selected_code = session.get("selected_material_code")
        selection = (
            build_material_selection(session["station_id"], selected_code)
            if selected_code
            else None
        )
        if selection is not None and not selection.success:
            session.pop("selected_material_code", None)
            session.pop("active_material_tag", None)
            selection = None

    active_payload = session.get("active_material_tag")
    reweigh_transaction_id = session.get("reweigh_original_transaction_id")
    queue = (
        build_material_queue(
            session["station_id"],
            active_payload,
            require_pending=False,
            expected_material_code=selection.material.code,
            reweigh_transaction_id=reweigh_transaction_id,
        )
        if active_payload and selection
        else None
    )
    if queue is not None and not queue.success:
        session.pop("active_material_tag", None)
        queue = None
    display_items = []
    if selection is not None:
        display_items.extend(selection.items)
    if queue is not None:
        display_items.extend(queue.items)
    display_transactions = list(
        {
            item.transaction.id: item.transaction
            for item in display_items
            if item.transaction is not None
        }.values()
    )
    replaced_transactions_by_id, weighed_users_by_id = _replacement_display_context(
        display_transactions
    )
    return render_template(
        "weighing/material.html",
        queue=queue,
        selection=selection,
        overview=overview,
        weight_form=MaterialQueueWeightForm(),
        weighing_station=db.session.get(Station, session["station_id"]),
        reweigh_form=ReweighForm(),
        reweigh_transaction_id=reweigh_transaction_id,
        reweigh_workflow_attempt=session.get("reweigh_workflow_attempt"),
        replaced_transactions_by_id=replaced_transactions_by_id,
        weighed_users_by_id=weighed_users_by_id,
        reweighed_material_context=reweighed_material_context,
    )


@bp.post("/material/validate")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def validate_material_mode():
    payload = request.get_json(silent=True) or {}
    material_tag = payload.get("material_tag")
    selected_code = payload.get("selected_material_code")
    selection = build_material_selection(session["station_id"], selected_code)
    if not selection.success:
        session.pop("active_material_tag", None)
        return jsonify(
            {
                "result": "UN-MATCH",
                "code": selection.code,
                "message": ui_message(selection.message),
            }
        ), 400
    queue = build_material_queue(
        session["station_id"],
        material_tag,
        expected_material_code=selection.material.code,
    )
    if queue.success:
        session["selected_material_code"] = selection.material.code
        session["active_material_tag"] = queue.tag.raw_payload
        session["weighing_mode"] = "material"
    else:
        session.pop("active_material_tag", None)
    return jsonify(
        {
            "result": "MATCH" if queue.success else "UN-MATCH",
            "code": queue.code,
            "message": ui_message(queue.message),
            "queue_count": len(queue.items),
            "selected_material_code": selection.material.code,
            "scanned_material_code": queue.tag.material_code if queue.tag else None,
        }
    )


@bp.post("/material/order/<int:po_id>/line/<int:formula_item_id>")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def weigh_material_queue_item(po_id, formula_item_id):
    form = MaterialQueueWeightForm()
    active_payload = session.get("active_material_tag")
    selected_code = session.get("selected_material_code")
    if not active_payload or not selected_code:
        flash(ui_message("Scan and validate a Material Tag before weighing."), "danger")
        return redirect(url_for("weighing.material_mode"))
    if form.validate_on_submit():
        result = save_material_queue_item(
            session["station_id"],
            po_id,
            formula_item_id,
            active_payload,
            form.actual_weight.data,
            current_user.id,
            expected_material_code=selected_code,
            replaces_transaction_id=session.get("reweigh_original_transaction_id"),
            reweigh_reason=session.get("reweigh_reason"),
        )
        flash(ui_message(result.message), "success" if result.success else "danger")
        if result.success:
            session.pop("reweigh_original_transaction_id", None)
            session.pop("reweigh_reason", None)
            session.pop("reweigh_workflow_attempt", None)
            session["weighing_mode"] = "material"
            return redirect(url_for("weighing.sticker", transaction_id=result.transaction.id))
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(ui_message(message), "danger")
    return redirect(url_for("weighing.material_mode"))


@bp.post("/material/end")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def end_material_session():
    session.pop("active_material_tag", None)
    session.pop("selected_material_code", None)
    session.pop("weighing_mode", None)
    overview = active_work_set_overview(session["station_id"])
    if overview.is_complete:
        flash(
            ui_message("All required weighings are complete. Complete this weighing session."),
            "success",
        )
    else:
        flash(ui_message("Material session ended. Scan the next Material Tag."), "success")
    return redirect(url_for("weighing.material_mode"))
