from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import (
    Formula,
    FormulaItem,
    Material,
    Product,
    ProductionOrder,
    RawMaterialLot,
    Station,
    User,
)

bp = Blueprint("master_data", __name__, url_prefix="/master-data")


@bp.get("/")
@login_required
@station_required
@roles_required("ADMIN")
def index():
    data = {
        "users": db.session.scalars(select(User).order_by(User.username)).all(),
        "stations": db.session.scalars(select(Station).order_by(Station.code)).all(),
        "materials": db.session.scalars(select(Material).order_by(Material.code)).all(),
        "raw_material_lots": db.session.scalars(
            select(RawMaterialLot).order_by(RawMaterialLot.lot_no)
        ).all(),
        "products": db.session.scalars(select(Product).order_by(Product.code)).all(),
        "formulas": db.session.scalars(select(Formula).order_by(Formula.code)).all(),
        "formula_items": db.session.scalars(
            select(FormulaItem).order_by(FormulaItem.formula_id, FormulaItem.line_no)
        ).all(),
        "production_orders": db.session.scalars(
            select(ProductionOrder).order_by(ProductionOrder.po_no)
        ).all(),
    }
    return render_template("master_data/index.html", **data)
