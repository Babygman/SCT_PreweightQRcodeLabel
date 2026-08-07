import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AuditLog,
    FormulaItem,
    ProductionOrder,
    WeighingTransaction,
    utcnow,
)


class MaterialTagError(ValueError):
    pass


@dataclass(frozen=True)
class MaterialTag:
    raw_payload: str
    receiving_date: datetime
    purchase_order: str
    purchase_order_line: str
    material_code: str
    delivery_invoice: str
    vendor_lot: str
    supplier: str
    comment: str
    warehouse: str
    location: str
    shelf: str


@dataclass(frozen=True)
class WeighingResult:
    success: bool
    code: str
    message: str
    transaction: WeighingTransaction | None = None


def parse_material_tag(payload):
    if not isinstance(payload, str):
        raise MaterialTagError("Material Tag QR must contain exactly 11 fields.")
    raw_payload = payload.strip()
    fields = raw_payload.split("|")
    if len(fields) != 11:
        raise MaterialTagError("Material Tag QR must contain exactly 11 fields.")
    fields = [field.strip() for field in fields]
    try:
        receiving_date = datetime.strptime(fields[0], "%d/%m/%Y")
    except ValueError as exc:
        raise MaterialTagError("Material Tag receiving date must use DD/MM/YYYY.") from exc
    if receiving_date.strftime("%d/%m/%Y") != fields[0]:
        raise MaterialTagError("Material Tag receiving date must use DD/MM/YYYY.")
    return MaterialTag(raw_payload, receiving_date, *fields[1:])


def _actual_weight(value):
    try:
        weight = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Actual Weight must be numeric and greater than zero.") from exc
    if not weight.is_finite():
        raise ValueError("Actual Weight must be numeric and greater than zero.")
    weight = weight.quantize(Decimal("0.001"))
    if weight <= 0:
        raise ValueError("Actual Weight must be numeric and greater than zero.")
    return weight


def _next_preweight_id(timestamp):
    prefix = f"PW-{timestamp:%Y%m%d}-"
    statement = select(func.max(WeighingTransaction.preweight_id)).where(
        WeighingTransaction.preweight_id.like(f"{prefix}%")
    )
    if db.session.get_bind().dialect.name == "mssql":
        statement = statement.with_hint(
            WeighingTransaction, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"
        )
    latest = db.session.scalar(statement)
    sequence = int(latest[-6:]) + 1 if latest else 1
    if sequence > 999999:
        raise RuntimeError("Daily Preweight ID sequence is exhausted.")
    return f"{prefix}{sequence:06d}"


def _wrong_material_audit(po, item, tag, user_id, station_id):
    db.session.add(
        AuditLog(
            event_type="WEIGHING_MATERIAL_MISMATCH",
            entity_type="FormulaItem",
            entity_id=str(item.id),
            user_id=user_id,
            station_id=station_id,
            occurred_at_utc=utcnow(),
            detail=(
                f"po={po.po_no}; line={item.line_no}; expected={item.material.code}; "
                f"scanned={tag.material_code}"
            ),
        )
    )
    db.session.commit()


def validate_material_tag(po_id, formula_item_id, material_tag_payload):
    try:
        tag = parse_material_tag(material_tag_payload)
    except MaterialTagError as exc:
        return WeighingResult(False, "INVALID_MATERIAL_TAG", str(exc))

    po = db.session.get(ProductionOrder, po_id)
    item = db.session.get(FormulaItem, formula_item_id)
    if po is None or po.status != "READY" or po.formula_id is None:
        return WeighingResult(False, "PO_NOT_READY", "Production Order is not ready for weighing.")
    if item is None or item.formula_id != po.formula_id:
        return WeighingResult(False, "FORMULA_LINE_MISMATCH", "Formula line is unavailable.")
    if tag.material_code != item.material.code:
        return WeighingResult(
            False,
            "WRONG_MATERIAL",
            f"Wrong Material: expected {item.material.code}, scanned {tag.material_code}.",
        )
    return WeighingResult(True, "MATCH", f"MATCH — {item.material.code}")


def save_weighing(po_id, formula_item_id, material_tag_payload, actual_weight, user_id, station_id):
    try:
        tag = parse_material_tag(material_tag_payload)
    except MaterialTagError as exc:
        return WeighingResult(False, "INVALID_MATERIAL_TAG", str(exc))
    try:
        weight = _actual_weight(actual_weight)
    except ValueError as exc:
        return WeighingResult(False, "INVALID_WEIGHT", str(exc))

    po = db.session.get(ProductionOrder, po_id)
    item = db.session.get(FormulaItem, formula_item_id)
    if po is None or po.status != "READY" or po.formula_id is None:
        return WeighingResult(False, "PO_NOT_READY", "Production Order is not ready for weighing.")
    if item is None or item.formula_id != po.formula_id:
        return WeighingResult(False, "FORMULA_LINE_MISMATCH", "Formula line is unavailable.")
    if tag.material_code != item.material.code:
        _wrong_material_audit(po, item, tag, user_id, station_id)
        return WeighingResult(
            False,
            "WRONG_MATERIAL",
            f"Wrong Material: expected {item.material.code}, scanned {tag.material_code}.",
        )

    existing = db.session.scalar(
        select(WeighingTransaction).where(
            WeighingTransaction.production_order_id == po.id,
            WeighingTransaction.formula_item_id == item.id,
            WeighingTransaction.status.in_(("COMPLETED", "CONSUMED")),
        )
    )
    if existing is not None:
        return WeighingResult(
            False,
            "FORMULA_LINE_ALREADY_WEIGHED",
            "This Formula line has already been weighed successfully.",
            existing,
        )

    weighed_at = utcnow()
    preweight_id = _next_preweight_id(weighed_at)
    erp_qr_payload = json.dumps(
        {
            "type": "SCT_PREWEIGHT",
            "version": 1,
            "preweight_id": preweight_id,
            "production_order": po.po_no,
            "production_lot": po.production_lot,
            "formula_sheet": po.formula.code,
            "item_code": item.material.code,
            "item_name": item.material.name,
            "actual_weight": f"{weight:.3f}",
            "unit": item.unit,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    transaction = WeighingTransaction(
        preweight_id=preweight_id,
        production_order_id=po.id,
        formula_item_id=item.id,
        raw_material_lot_id=None,
        material_tag_raw_payload=tag.raw_payload,
        receiving_date_snapshot=tag.receiving_date.date(),
        purchase_order_snapshot=tag.purchase_order,
        purchase_order_line_snapshot=tag.purchase_order_line,
        material_code_snapshot=tag.material_code,
        delivery_invoice_snapshot=tag.delivery_invoice,
        vendor_lot_snapshot=tag.vendor_lot,
        supplier_snapshot=tag.supplier,
        comment_snapshot=tag.comment,
        warehouse_snapshot=tag.warehouse,
        location_snapshot=tag.location,
        shelf_snapshot=tag.shelf,
        erp_qr_payload=erp_qr_payload,
        target_weight_snapshot=item.target_weight,
        actual_weight=weight,
        unit_snapshot=item.unit,
        station_id=station_id,
        weighed_by_user_id=user_id,
        weighed_at_utc=weighed_at,
        status="COMPLETED",
    )
    db.session.add(transaction)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return WeighingResult(
            False,
            "SAVE_CONFLICT",
            "The Formula line or Preweight ID was saved by another request. Refresh and retry.",
        )
    return WeighingResult(
        True,
        "COMPLETED",
        f"Weighing completed as {transaction.preweight_id}.",
        transaction,
    )
