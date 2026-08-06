from dataclasses import dataclass

from sqlalchemy import select

from app.extensions import db
from app.models import AuditLog, Formula, ProductionOrder, utcnow


@dataclass(frozen=True)
class PreparationResult:
    success: bool
    code: str
    message: str
    production_order: ProductionOrder | None = None


def _document_code(scanned_value, prefix):
    value = scanned_value.strip()
    marker = f"{prefix}|"
    return value[len(marker) :].strip() if value.upper().startswith(marker) else value


def _failed_scan(code, message, po, user_id, station_id, po_no, formula_code):
    db.session.add(
        AuditLog(
            event_type="PO_FORMULA_SCAN_FAIL",
            entity_type="ProductionOrder",
            entity_id=po.po_no if po else po_no,
            user_id=user_id,
            station_id=station_id,
            occurred_at_utc=utcnow(),
            detail=f"reason={code}; po={po_no}; formula={formula_code}",
        )
    )
    db.session.commit()
    return PreparationResult(False, code, message, po)


def prepare_production_order(po_no, formula_code, user_id, station_id=None):
    po_no = _document_code(po_no, "SCTPO")
    formula_code = _document_code(formula_code, "SCTFS")
    po = db.session.scalar(select(ProductionOrder).where(ProductionOrder.po_no == po_no))
    if po is None:
        return _failed_scan(
            "PO_NOT_FOUND",
            "Production Order not found.",
            None,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if po.status == "CANCELLED":
        return _failed_scan(
            "PO_CANCELLED",
            "Cancelled Production Order cannot start.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if po.status == "COMPLETED":
        return _failed_scan(
            "PO_COMPLETED",
            "Completed Production Order cannot start.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )

    formula = db.session.scalar(select(Formula).where(Formula.code == formula_code))
    if formula is None:
        return _failed_scan(
            "FORMULA_NOT_FOUND",
            "Formula Sheet not found.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if not formula.is_active:
        return _failed_scan(
            "FORMULA_UNAVAILABLE",
            "Formula Sheet is unavailable.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if po.formula_id is not None and po.formula_id != formula.id:
        return _failed_scan(
            "WRONG_FORMULA",
            "ERROR: Production Order and Formula Sheet do not match.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if formula.product_id != po.product_id:
        return _failed_scan(
            "WRONG_FORMULA",
            "ERROR: Production Order and Formula Sheet do not match.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if formula.production_lot is not None and formula.production_lot != po.production_lot:
        return _failed_scan(
            "WRONG_PRODUCTION_LOT",
            "ERROR: Production Lot does not match the Formula Sheet.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )
    if po.status == "READY" and po.formula_id != formula.id:
        return _failed_scan(
            "WRONG_FORMULA",
            "ERROR: Production Order and Formula Sheet do not match.",
            po,
            user_id,
            station_id,
            po_no,
            formula_code,
        )

    if po.status == "OPEN":
        po.formula_id = formula.id
        po.status = "READY"
        po.prepared_by_user_id = user_id
        po.prepared_at_utc = utcnow()
        db.session.commit()

    return PreparationResult(
        True, "READY", "Production Order and Formula Sheet matched; ready for weighing.", po
    )
