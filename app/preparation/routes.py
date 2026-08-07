from flask import Blueprint, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required

from app.auth.decorators import roles_required, station_required
from app.services.workset import (
    active_work_set_overview,
    close_active_work_set,
    prepare_work_set_order,
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
    overview = active_work_set_overview(session["station_id"])
    return render_template(
        "preparation/prepare.html",
        form=form,
        result=result,
        prepared_orders=overview.orders,
        progress=overview.progress,
    )


@bp.post("/work-set/close")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def close_work_set():
    count = close_active_work_set(session["station_id"])
    session.pop("active_material_tag", None)
    session.pop("weighing_mode", None)
    flash(
        f"Cancelled this weighing session ({count} Production Order(s) removed). "
        "Production Order statuses and weighing records were not changed.",
        "success",
    )
    return redirect(url_for("preparation.prepare"))
