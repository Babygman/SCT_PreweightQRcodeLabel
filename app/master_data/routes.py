from functools import wraps
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.auth.decorators import roles_required, station_required
from app.extensions import db
from app.models import (
    Formula,
    FormulaItem,
    Material,
    MaterialImportBatch,
    Product,
    ProductionOrder,
    RawMaterialLot,
    Station,
    User,
)
from app.services.material_import import (
    MaterialImportError,
    apply_material_import,
    create_material_import_preview,
)

from .forms import MaterialImportApplyForm, MaterialImportUploadForm

bp = Blueprint("master_data", __name__, url_prefix="/master-data")


def material_import_enabled_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config.get("MATERIAL_TAG_ISSUANCE_ENABLED", False):
            abort(404)
        return view(*args, **kwargs)

    return wrapped


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


@bp.route("/material-import", methods=["GET", "POST"])
@material_import_enabled_required
@login_required
@station_required
@roles_required("ADMIN")
def material_import_upload():
    form = MaterialImportUploadForm()
    if not form.idempotency_key.data:
        form.idempotency_key.data = str(uuid4())
    if form.validate_on_submit():
        workbook = form.workbook.data
        file_bytes = workbook.read(current_app.config["MATERIAL_IMPORT_MAX_BYTES"] + 1)
        batch = create_material_import_preview(
            file_bytes=file_bytes,
            filename=workbook.filename,
            idempotency_key=form.idempotency_key.data,
            user_id=current_user.id,
            station_id=session["station_id"],
            maximum_bytes=current_app.config["MATERIAL_IMPORT_MAX_BYTES"],
            maximum_rows=current_app.config["MATERIAL_IMPORT_MAX_ROWS"],
            maximum_uncompressed_bytes=current_app.config["MATERIAL_IMPORT_MAX_UNCOMPRESSED_BYTES"],
        )
        return redirect(url_for("master_data.material_import_preview", batch_id=batch.id))
    return render_template("master_data/material_import_upload.html", form=form)


@bp.get("/material-import/<int:batch_id>")
@material_import_enabled_required
@login_required
@station_required
@roles_required("ADMIN")
def material_import_preview(batch_id):
    batch = db.get_or_404(MaterialImportBatch, batch_id)
    rows = sorted(batch.rows, key=lambda row: row.row_number)
    return render_template(
        "master_data/material_import_result.html",
        batch=batch,
        rows=rows,
        apply_form=MaterialImportApplyForm(),
    )


@bp.post("/material-import/<int:batch_id>/apply")
@material_import_enabled_required
@login_required
@station_required
@roles_required("ADMIN")
def material_import_apply(batch_id):
    form = MaterialImportApplyForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        batch = apply_material_import(
            batch_id=batch_id,
            user_id=current_user.id,
            station_id=session["station_id"],
        )
    except MaterialImportError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("master_data.material_import_preview", batch_id=batch_id))
    flash("Material Master import applied successfully.", "success")
    return redirect(url_for("master_data.material_import_preview", batch_id=batch.id))
