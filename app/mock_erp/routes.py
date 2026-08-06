from io import BytesIO

import qrcode
from flask import abort, current_app, flash, redirect, render_template, send_file, url_for
from flask_login import login_required
from sqlalchemy import select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import Formula, ProductionOrder
from app.services.mock_erp import MockDocumentError, create_mock_order

from . import bp
from .forms import MockOrderForm


def _enabled():
    if not current_app.config.get("MOCK_ERP_ENABLED", False):
        abort(404)


@bp.route("/", methods=["GET", "POST"])
@login_required
@station_required
@roles_required("SUPERVISOR", "ADMIN")
def index():
    _enabled()
    form = MockOrderForm()
    if form.validate_on_submit():
        try:
            order = create_mock_order(
                po_no=form.po_no.data.strip(),
                product_code=form.product_code.data.strip(),
                product_name=form.product_name.data.strip(),
                production_lot=form.production_lot.data.strip(),
                quantity=form.quantity.data,
                formula_code=form.formula_code.data.strip(),
                production_date=form.production_date.data,
                expected_finish_date=form.expected_finish_date.data,
            )
        except MockDocumentError as exc:
            flash(str(exc), "danger")
        else:
            flash("Mock Production Order and Formula Sheet created.", "success")
            return redirect(url_for("mock_erp.detail", po_id=order.id))
    orders = db.session.scalars(
        select(ProductionOrder)
        .where(ProductionOrder.quantity.is_not(None))
        .order_by(ProductionOrder.id.desc())
    ).all()
    return render_template("mock_erp/index.html", form=form, orders=orders)


@bp.get("/<int:po_id>")
@login_required
@station_required
@roles_required("SUPERVISOR", "ADMIN")
def detail(po_id):
    _enabled()
    order = db.get_or_404(ProductionOrder, po_id)
    return render_template("mock_erp/detail.html", order=order)


@bp.get("/<int:po_id>/production-order")
@login_required
@station_required
@roles_required("SUPERVISOR", "ADMIN")
def production_order_document(po_id):
    _enabled()
    order = db.get_or_404(ProductionOrder, po_id)
    return render_template("mock_erp/production_order.html", order=order)


@bp.get("/<int:po_id>/formula-sheet")
@login_required
@station_required
@roles_required("SUPERVISOR", "ADMIN")
def formula_sheet_document(po_id):
    _enabled()
    order = db.get_or_404(ProductionOrder, po_id)
    if order.formula is None:
        abort(404)
    return render_template("mock_erp/formula_sheet.html", order=order)


@bp.get("/qr/<string:kind>/<int:record_id>.png")
@login_required
@station_required
@roles_required("SUPERVISOR", "ADMIN")
def qr_image(kind, record_id):
    _enabled()
    if kind == "po":
        record = db.session.get(ProductionOrder, record_id)
        payload = f"SCTPO|{record.po_no}" if record else None
    elif kind == "formula":
        record = db.session.get(Formula, record_id)
        payload = f"SCTFS|{record.code}" if record else None
    else:
        payload = None
    if payload is None:
        abort(404)
    image = qrcode.make(payload)
    stream = BytesIO()
    image.save(stream, format="PNG")
    stream.seek(0)
    return send_file(stream, mimetype="image/png", max_age=0)
