from flask import Blueprint, flash, render_template
from flask_login import current_user, login_required

from app.auth.decorators import roles_required, station_required
from app.services.preparation import prepare_production_order

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
        result = prepare_production_order(
            form.po_no.data.strip(), form.formula_code.data.strip(), current_user.id
        )
        flash(result.message, "success" if result.success else "danger")
    return render_template("preparation/prepare.html", form=form, result=result)
