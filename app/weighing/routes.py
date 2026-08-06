from flask import abort, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import ProductionOrder, WeighingTransaction
from app.services.weighing import save_weighing

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
    else:
        for messages in form.errors.values():
            for message in messages:
                flash(message, "danger")
    return redirect(url_for("weighing.order", po_id=po_id))
