from io import BytesIO

import qrcode
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from sqlalchemy import or_, select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import FinishGoodsProfile, Formula, Product, ProductionOrder
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
    finish_goods_enabled = current_app.config.get("FINISHED_GOODS_MASTER_ENABLED", False)
    finish_goods_pagination = None
    search_query = request.args.get("finish_goods_q", "").strip()
    if finish_goods_enabled:
        active_statement = (
            select(Product)
            .join(FinishGoodsProfile)
            .where(
                Product.is_active == True,  # noqa: E712
                FinishGoodsProfile.source_category_no == "F/G",
            )
        )
        selectable = db.session.scalars(active_statement.order_by(Product.code)).all()
        form.product_id.choices = [(0, "Select a Finish Good")]
        form.product_id.choices.extend(
            (product.id, f"{product.code} — {product.name}") for product in selectable
        )
        result_statement = active_statement
        if search_query:
            pattern = f"%{search_query}%"
            result_statement = result_statement.where(
                or_(Product.code.ilike(pattern), Product.name.ilike(pattern))
            )
        finish_goods_pagination = db.paginate(
            result_statement.order_by(Product.code, Product.id),
            page=request.args.get("page", 1, type=int),
            per_page=current_app.config["FINISHED_GOODS_SEARCH_PAGE_SIZE"],
            max_per_page=current_app.config["FINISHED_GOODS_SEARCH_PAGE_SIZE"],
            error_out=False,
        )
    valid_submission = form.validate_on_submit()
    if valid_submission and finish_goods_enabled and not form.product_id.data:
        form.product_id.errors.append("Select an Active Finish Good from the approved Master.")
        valid_submission = False
    if (
        valid_submission
        and not finish_goods_enabled
        and (not form.product_code.data.strip() or not form.product_name.data.strip())
    ):
        flash("Finished Good Item Code and Name are required.", "danger")
        valid_submission = False
    if valid_submission:
        try:
            order = create_mock_order(
                po_no=form.po_no.data.strip(),
                product_id=form.product_id.data if finish_goods_enabled else None,
                product_code=form.product_code.data.strip() if not finish_goods_enabled else None,
                product_name=form.product_name.data.strip() if not finish_goods_enabled else None,
                production_lot=form.production_lot.data.strip(),
                quantity=form.quantity.data,
                formula_code=form.formula_code.data.strip(),
                production_date=form.production_date.data,
                expected_finish_date=form.expected_finish_date.data,
            )
        except MockDocumentError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("mock_erp.index"))
        else:
            flash("Mock Production Order and Formula Sheet created.", "success")
            return redirect(url_for("mock_erp.detail", po_id=order.id))
    orders = db.session.scalars(
        select(ProductionOrder)
        .where(ProductionOrder.quantity.is_not(None))
        .order_by(ProductionOrder.id.desc())
    ).all()
    return render_template(
        "mock_erp/index.html",
        form=form,
        orders=orders,
        finish_goods_enabled=finish_goods_enabled,
        finish_goods_pagination=finish_goods_pagination,
        finish_goods_q=search_query,
    )


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
