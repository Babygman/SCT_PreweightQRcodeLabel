from flask import Blueprint, abort, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required

from app.auth.decorators import roles_required, station_required
from app.services.workset import (
    active_work_set_overview,
    cancel_active_work_set,
    complete_work_set,
    completed_work_set_summary,
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
    overview = active_work_set_overview(session["station_id"])
    if form.validate_on_submit():
        if overview.is_complete:
            flash(
                "All required weighings are complete. Complete this weighing session.",
                "success",
            )
        else:
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
        overview=overview,
        prepared_orders=overview.orders,
        progress=overview.progress,
    )


@bp.post("/work-set/close")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def close_work_set():
    result = cancel_active_work_set(session["station_id"])
    if result.success:
        session.pop("active_material_tag", None)
        session.pop("weighing_mode", None)
    flash(result.message, "success" if result.success else "danger")
    return redirect(url_for("preparation.prepare"))


@bp.post("/session/<session_code>/complete")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def complete_session(session_code):
    result = complete_work_set(
        session_code, current_user.id, session["station_id"]
    )
    flash(result.message, "success" if result.success else "danger")
    if not result.success:
        return redirect(url_for("preparation.prepare"))
    session.pop("active_material_tag", None)
    session.pop("weighing_mode", None)
    return redirect(
        url_for("preparation.completed_session", session_code=session_code)
    )


@bp.get("/session/<session_code>/completed")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def completed_session(session_code):
    summary = completed_work_set_summary(session_code, session["station_id"])
    if summary is None:
        abort(404)
    return render_template("preparation/completed.html", summary=summary)
