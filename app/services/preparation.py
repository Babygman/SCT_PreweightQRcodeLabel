from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import Formula, ProductionOrder, utcnow


@dataclass(frozen=True)
class PreparationResult:
    success: bool
    code: str
    message: str
    production_order: ProductionOrder | None = None


def prepare_production_order(po_no, formula_code, user_id):
    po = db.session.scalar(select(ProductionOrder).where(ProductionOrder.po_no == po_no))
    if po is None:
        return PreparationResult(False, "PO_NOT_FOUND", "Production Order not found.")
    if po.status == "CANCELLED":
        return PreparationResult(
            False, "PO_CANCELLED", "Cancelled Production Order cannot start.", po
        )
    if po.status == "COMPLETED":
        return PreparationResult(
            False, "PO_COMPLETED", "Completed Production Order cannot start.", po
        )

    formula = db.session.scalar(select(Formula).where(Formula.code == formula_code))
    if formula is None:
        return PreparationResult(False, "FORMULA_NOT_FOUND", "Formula not found.", po)
    if not formula.is_active:
        return PreparationResult(False, "FORMULA_UNAVAILABLE", "Formula is unavailable.", po)
    if formula.product_id != po.product_id:
        return PreparationResult(
            False, "WRONG_FORMULA", "Formula does not match the Production Order product.", po
        )
    if po.status == "READY" and po.formula_id != formula.id:
        return PreparationResult(
            False, "WRONG_FORMULA", "Production Order is already prepared with another formula.", po
        )

    if po.status == "OPEN":
        po.formula_id = formula.id
        po.status = "READY"
        po.prepared_by_user_id = user_id
        po.prepared_at_utc = utcnow()
        db.session.commit()

    return PreparationResult(True, "READY", "Production Order is ready for weighing.", po)
