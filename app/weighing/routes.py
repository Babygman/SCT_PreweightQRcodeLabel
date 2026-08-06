from flask import abort, render_template
from flask_login import login_required

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import ProductionOrder

from . import bp


@bp.get("/order/<int:po_id>")
@login_required
@station_required
@roles_required("OPERATOR", "SUPERVISOR", "ADMIN")
def order(po_id):
    production_order = db.get_or_404(ProductionOrder, po_id)
    if production_order.status != "READY" or production_order.formula is None:
        abort(403)
    return render_template("weighing/order.html", order=production_order)
