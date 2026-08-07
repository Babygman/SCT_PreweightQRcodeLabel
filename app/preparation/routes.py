from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required

from app.auth.decorators import roles_required, station_required
from app.services.workset import (
    active_work_set_orders,
    close_active_work_set,
    prepare_work_set_order,
    work_set_progress,
)

from .forms import PreparationForm

bp = Blueprint("preparation", __name__, url_prefix="/preparation")


@bp.route("/", methods=["GET", "POST"])
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def prepare():
    form = PreparationForm()
    result = None
    if form.validate_on_submit():
        result = prepare_work_set_order(
            form.po_no.data.strip(),
            form.formula_code.data.strip(),
            current_user.id,
            session.get("station_id"),
        )
        flash(result.message, "success" if result.success else "danger")
        if result.success:
            form.po_no.data = ""
            form.formula_code.data = ""
    prepared_orders = active_work_set_orders(session["station_id"])
    progress = {order.id: work_set_progress(order) for order in prepared_orders}
    return render_template(
        "preparation/prepare.html",
        form=form,
        result=result,
        prepared_orders=prepared_orders,
        progress=progress,
    )


@bp.post("/work-set/close")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def close_work_set():
    count = close_active_work_set(session["station_id"])
    session.pop("active_material_tag", None)
    session.pop("weighing_mode", None)
    flash(f"Closed Active Work Set ({count} Production Order(s)).", "success")
    return redirect(url_for("preparation.prepare"))
