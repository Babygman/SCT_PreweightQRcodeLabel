import json
from io import BytesIO

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
from app.models import ProductionOrder, WeighingTransaction
from app.services.weighing import save_weighing, validate_material_tag

from . import bp
from .forms import WeighingForm


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
        )
    ).all()
    transactions_by_item = {
        transaction.formula_item_id: transaction for transaction in transactions
    }
    return render_template(
        "weighing/order.html",
        order=production_order,
        form=WeighingForm(),
        transactions_by_item=transactions_by_item,
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
        flash(result.message, "success" if result.success else "danger")
        if result.success:
            return redirect(url_for("weighing.sticker", transaction_id=result.transaction.id))
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(message, "danger")
    return redirect(url_for("weighing.order", po_id=po_id))


@bp.post("/order/<int:po_id>/line/<int:formula_item_id>/validate-material")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def validate_material(po_id, formula_item_id):
    payload = request.get_json(silent=True) or {}
    result = validate_material_tag(po_id, formula_item_id, payload.get("material_tag"))
    return jsonify(
        {
            "result": "MATCH" if result.success else "UN-MATCH",
            "code": result.code,
            "message": result.message,
        }
    )


@bp.get("/transaction/<int:transaction_id>/sticker")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def sticker(transaction_id):
    transaction = db.get_or_404(WeighingTransaction, transaction_id)
    if not transaction.erp_qr_payload:
        abort(404)
    return render_template(
        "weighing/sticker.html",
        transaction=transaction,
        payload=json.loads(transaction.erp_qr_payload),
    )


@bp.get("/transaction/<int:transaction_id>/qr.png")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def sticker_qr(transaction_id):
    transaction = db.get_or_404(WeighingTransaction, transaction_id)
    if not transaction.erp_qr_payload:
        abort(404)
    image = qrcode.make(transaction.erp_qr_payload)
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return send_file(stream, mimetype="image/png", max_age=0)
