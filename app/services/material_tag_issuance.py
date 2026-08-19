import base64
import calendar
import json
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from io import BytesIO
from uuid import uuid4
from zoneinfo import ZoneInfo

import qrcode
from flask import current_app
from qrcode.constants import ERROR_CORRECT_M
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagDraft,
    MaterialTagPrintEvent,
    utcnow,
)
from app.presentation import parse_user_date
from app.services.weighing import MaterialTagError, parse_material_tag

WEIGHT_QUANTUM = Decimal("0.001")
DEFAULT_MAXIMUM_TAGS = 200
MAX_BATCH_NUMBER_ATTEMPTS = 10
MAX_PRINTABLE_MATERIAL_NAME = 100


class MaterialTagIssuanceError(ValueError):
    """Raised when foundational Material Tag issuance input is invalid."""


@dataclass(frozen=True)
class ContainerWeightPlan:
    total_received_weight: Decimal
    standard_container_weight: Decimal
    weights: tuple[Decimal, ...]
    full_tag_count: int
    remainder_weight: Decimal

    @property
    def tag_count(self):
        return len(self.weights)

    def json_values(self):
        """Return stable three-decimal strings suitable for JSON serialization."""
        return tuple(f"{weight:.3f}" for weight in self.weights)

    def to_json(self):
        return json.dumps(self.json_values(), separators=(",", ":"))


def _weight(value, field_name):
    if isinstance(value, (float, bool)) or value is None:
        raise MaterialTagIssuanceError(
            f"{field_name} must be a finite Decimal-compatible value with at most three decimals."
        )
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as exc:
        raise MaterialTagIssuanceError(
            f"{field_name} must be a finite Decimal-compatible value with at most three decimals."
        ) from exc
    if not parsed.is_finite():
        raise MaterialTagIssuanceError(f"{field_name} must be finite and greater than zero.")
    if parsed.as_tuple().exponent < -3:
        raise MaterialTagIssuanceError(f"{field_name} may contain no more than three decimals.")
    if parsed <= 0:
        raise MaterialTagIssuanceError(f"{field_name} must be greater than zero.")
    return parsed.quantize(WEIGHT_QUANTUM)


def calculate_container_weights(
    total_received_weight, standard_container_weight, maximum_tags=DEFAULT_MAXIMUM_TAGS
):
    """Split an exact received weight into immutable three-decimal container weights."""
    if isinstance(maximum_tags, bool) or not isinstance(maximum_tags, int):
        raise MaterialTagIssuanceError("Maximum Tags must be an integer between 1 and 200.")
    if not 1 <= maximum_tags <= DEFAULT_MAXIMUM_TAGS:
        raise MaterialTagIssuanceError("Maximum Tags must be an integer between 1 and 200.")

    total = _weight(total_received_weight, "Total Received Weight")
    standard = _weight(standard_container_weight, "Standard Container Weight")
    full_count = int((total / standard).to_integral_value(rounding=ROUND_FLOOR))
    remainder = total - (standard * full_count)
    weights = (standard,) * full_count
    if remainder > 0:
        weights += (remainder,)

    if not weights or len(weights) > maximum_tags:
        raise MaterialTagIssuanceError(
            f"Calculated Tag count must be between 1 and {maximum_tags}."
        )
    if any(weight <= 0 for weight in weights) or sum(weights, Decimal("0.000")) != total:
        raise MaterialTagIssuanceError(
            "Calculated container weights do not reconcile to Total Received Weight."
        )
    return ContainerWeightPlan(total, standard, weights, full_count, remainder)


def calculate_expiry_date(receiving_date):
    """Return Receiving Date plus six calendar months, clamped, minus one day."""
    if type(receiving_date) is not date:
        raise MaterialTagIssuanceError("Receiving Date must be a valid date.")
    month_index = receiving_date.month - 1 + 6
    target_year = receiving_date.year + month_index // 12
    target_month = month_index % 12 + 1
    target_day = min(receiving_date.day, calendar.monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day) - timedelta(days=1)


def _qr_text(value, field_name, maximum_length, *, optional=False, uppercase=False):
    if value is None:
        if optional:
            return ""
        raise MaterialTagIssuanceError(f"{field_name} is required.")
    text_value = unicodedata.normalize("NFC", str(value)).strip()
    if not text_value and not optional:
        raise MaterialTagIssuanceError(f"{field_name} is required.")
    if "|" in text_value:
        raise MaterialTagIssuanceError(f"{field_name} must not contain '|'.")
    if any(unicodedata.category(character).startswith("C") for character in text_value):
        raise MaterialTagIssuanceError(f"{field_name} must not contain control characters.")
    if len(text_value) > maximum_length:
        raise MaterialTagIssuanceError(f"{field_name} must not exceed {maximum_length} characters.")
    return text_value.upper() if uppercase else text_value


def build_material_tag_qr_payload(
    *,
    receiving_date,
    purchase_order,
    purchase_order_line,
    material_code,
    delivery_invoice,
    vendor_lot,
    supplier,
    comment="",
    warehouse,
    location,
    shelf,
):
    """Build and verify the approved, unversioned eleven-field Material Tag QR payload."""
    if type(receiving_date) is not date:
        raise MaterialTagIssuanceError("Receiving Date must be a valid date.")
    fields = (
        receiving_date.strftime("%d/%m/%Y"),
        _qr_text(purchase_order, "Purchase Order", 100),
        _qr_text(purchase_order_line, "PO Line", 30),
        _qr_text(material_code, "Material Code", 50, uppercase=True),
        _qr_text(delivery_invoice, "Delivery Invoice", 100),
        _qr_text(vendor_lot, "Vendor Lot", 100),
        _qr_text(supplier, "Supplier", 100),
        _qr_text(comment, "Comment", 200, optional=True),
        _qr_text(warehouse, "Warehouse", 50),
        _qr_text(location, "Location", 50),
        _qr_text(shelf, "Shelf", 50),
    )
    payload = "|".join(fields)
    try:
        parsed = parse_material_tag(payload)
    except MaterialTagError as exc:
        raise MaterialTagIssuanceError(str(exc)) from exc
    if parsed.raw_payload != payload:
        raise MaterialTagIssuanceError("Generated Material Tag QR payload is not deterministic.")
    return payload


def _date(value):
    try:
        parsed = parse_user_date(value)
    except ValueError as exc:
        raise MaterialTagIssuanceError("Receiving Date must use dd/mm/yyyy.") from exc
    if not date(2000, 1, 1) <= parsed <= date(2100, 12, 31):
        raise MaterialTagIssuanceError("Receiving Date must be between 01/01/2000 and 31/12/2100.")
    return parsed


def _normalized_values(values, material):
    receiving = _date(values.get("receiving_date"))
    normalized = {
        "receiving_date": receiving,
        "purchase_order": _qr_text(values.get("purchase_order"), "Purchase Order", 100),
        "purchase_order_line": _qr_text(values.get("purchase_order_line"), "PO Line", 30),
        "material_code": _qr_text(material.code, "Material Code", 50, uppercase=True),
        "delivery_invoice": _qr_text(values.get("delivery_invoice"), "Delivery Invoice", 100),
        "vendor_lot": _qr_text(values.get("vendor_lot"), "Vendor Lot", 100),
        "supplier": _qr_text(values.get("supplier"), "Supplier", 100),
        "comment": _qr_text(values.get("comment"), "Comment", 200, optional=True),
        "warehouse": _qr_text(values.get("warehouse"), "Warehouse", 50),
        "location": _qr_text(values.get("location"), "Location", 50),
        "shelf": _qr_text(values.get("shelf"), "Shelf", 50),
    }
    plan = calculate_container_weights(
        values.get("total_received_weight"), values.get("standard_container_weight")
    )
    expiry = calculate_expiry_date(receiving)
    payload = build_material_tag_qr_payload(**normalized)
    return normalized, plan, expiry, payload


def _material(material_id, *, lock=False):
    try:
        identifier = int(material_id)
    except (TypeError, ValueError) as exc:
        raise MaterialTagIssuanceError("Select a valid active Material.") from exc
    statement = select(Material).where(Material.id == identifier)
    if lock:
        statement = statement.with_for_update().with_hint(
            Material, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql"
        )
    material = db.session.scalar(statement)
    if material is None or not material.is_active:
        raise MaterialTagIssuanceError("Select a valid active Material.")
    return material


def _audit(event_type, entity_type, entity_id, user_id, station_id, metadata):
    audit = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        user_id=user_id,
        station_id=station_id,
        occurred_at_utc=utcnow(),
        detail=json.dumps(metadata, ensure_ascii=True, separators=(",", ":")),
    )
    if db.session.get_bind().dialect.name == "sqlite":
        audit.id = db.session.scalar(select(func.coalesce(func.max(AuditLog.id), 0) + 1))
    db.session.add(audit)


def create_material_tag_draft(*, values, user_id, station_id, lifetime_minutes=60):
    if (
        isinstance(lifetime_minutes, bool)
        or not isinstance(lifetime_minutes, int)
        or lifetime_minutes < 1
    ):
        raise MaterialTagIssuanceError("Draft lifetime configuration is invalid.")
    material = _material(values.get("material_id"))
    normalized, plan, _expiry, _payload = _normalized_values(values, material)
    now = utcnow()
    draft = MaterialTagDraft(
        draft_token=str(uuid4()),
        idempotency_key=str(uuid4()),
        material_id=material.id,
        **normalized,
        total_received_weight=plan.total_received_weight,
        standard_container_weight=plan.standard_container_weight,
        calculated_tag_count=plan.tag_count,
        calculated_weights_json=plan.to_json(),
        status="PREVIEWED",
        created_by_user_id=user_id,
        created_at_utc=now,
        expires_at_utc=now + timedelta(minutes=lifetime_minutes),
    )
    db.session.add(draft)
    db.session.flush()
    _audit(
        "MATERIAL_TAG_PREVIEWED",
        "MATERIAL_TAG_DRAFT",
        draft.id,
        user_id,
        station_id,
        {
            "draft_token": draft.draft_token,
            "event": "MATERIAL_TAG_PREVIEWED",
            "material_code": draft.material_code,
            "vendor_lot": draft.vendor_lot,
            "tag_count": draft.calculated_tag_count,
            "total_weight": f"{draft.total_received_weight:.3f}",
            "status": draft.status,
        },
    )
    db.session.commit()
    return draft


def preview_details(draft):
    material = draft.material
    normalized, plan, expiry, payload = _normalized_values(
        {
            "receiving_date": draft.receiving_date,
            "purchase_order": draft.purchase_order,
            "purchase_order_line": draft.purchase_order_line,
            "delivery_invoice": draft.delivery_invoice,
            "vendor_lot": draft.vendor_lot,
            "supplier": draft.supplier,
            "comment": draft.comment,
            "warehouse": draft.warehouse,
            "location": draft.location,
            "shelf": draft.shelf,
            "total_received_weight": draft.total_received_weight,
            "standard_container_weight": draft.standard_container_weight,
        },
        material,
    )
    if (
        normalized["material_code"] != draft.material_code
        or plan.tag_count != draft.calculated_tag_count
        or plan.to_json() != draft.calculated_weights_json
    ):
        raise MaterialTagIssuanceError("Draft integrity validation failed.")
    return {"plan": plan, "expiry": expiry, "qr_payload": payload}


def _next_batch_number():
    business_date = datetime.now(ZoneInfo(current_app.config["APP_TIMEZONE"])).date()
    return f"MTB-{business_date.strftime('%Y%m%d')}-{secrets.randbelow(1_000_000):06d}"


def _draft_for_issue_statement(token):
    return (
        select(MaterialTagDraft)
        .where(MaterialTagDraft.draft_token == token)
        .with_for_update()
        .with_hint(MaterialTagDraft, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
    )


def issue_material_tag_draft(*, token, user_id, station_id, _collision_attempt=0):
    try:
        draft = db.session.scalar(_draft_for_issue_statement(token))
        if draft is None:
            raise MaterialTagIssuanceError("Material Tag draft was not found.")
        if draft.created_by_user_id != user_id:
            raise MaterialTagIssuanceError("Only the draft creator may confirm issuance.")
        if draft.status == "ISSUED" and draft.issued_batch_id:
            batch = db.session.get(MaterialTagBatch, draft.issued_batch_id)
            db.session.commit()
            return batch
        if draft.status != "PREVIEWED":
            raise MaterialTagIssuanceError("Only a previewed draft may be issued.")
        if draft.expires_at_utc <= utcnow():
            draft.status = "EXPIRED"
            db.session.commit()
            raise MaterialTagIssuanceError("This Material Tag draft has expired.")

        material = _material(draft.material_id, lock=True)
        details = preview_details(draft)
        plan = details["plan"]
        expiry = details["expiry"]
        payload = details["qr_payload"]
        if parse_material_tag(payload).raw_payload != payload:
            raise MaterialTagIssuanceError("Generated QR payload failed validation.")

        existing = db.session.scalar(
            select(MaterialTagBatch).where(MaterialTagBatch.source_draft_token == token)
        )
        if existing is not None:
            draft.status = "ISSUED"
            draft.issued_batch_id = existing.id
            db.session.commit()
            return existing

        batch = None
        for _attempt in range(MAX_BATCH_NUMBER_ATTEMPTS):
            candidate = _next_batch_number()
            if (
                db.session.scalar(
                    select(MaterialTagBatch.id).where(MaterialTagBatch.batch_no == candidate)
                )
                is None
            ):
                candidate_batch = MaterialTagBatch(
                    batch_no=candidate,
                    material_id=material.id,
                    material_code_snapshot=material.code,
                    material_name_snapshot=material.name,
                    unit_snapshot=material.unit,
                    category_no_snapshot=material.source_category_no,
                    receiving_date=draft.receiving_date,
                    expiry_date=expiry,
                    purchase_order=draft.purchase_order,
                    purchase_order_line=draft.purchase_order_line,
                    delivery_invoice=draft.delivery_invoice,
                    vendor_lot=draft.vendor_lot,
                    supplier=draft.supplier,
                    comment=draft.comment,
                    warehouse=draft.warehouse,
                    location=draft.location,
                    shelf=draft.shelf,
                    total_received_weight=plan.total_received_weight,
                    standard_container_weight=plan.standard_container_weight,
                    tag_count=plan.tag_count,
                    qr_payload=payload,
                    issued_by_user_id=user_id,
                    issued_at_utc=utcnow(),
                    source_draft_token=draft.draft_token,
                )
                batch = candidate_batch
                break
        if batch is None:
            raise MaterialTagIssuanceError(
                "A unique Material Tag batch number could not be generated."
            )
        db.session.add(batch)
        db.session.flush()
        created = utcnow()
        db.session.add_all(
            [
                MaterialTag(
                    batch_id=batch.id,
                    sequence_no=index,
                    container_weight=weight,
                    created_at_utc=created,
                )
                for index, weight in enumerate(plan.weights, 1)
            ]
        )
        draft.status = "ISSUED"
        draft.issued_batch_id = batch.id
        _audit(
            "MATERIAL_TAG_BATCH_ISSUED",
            "MATERIAL_TAG_BATCH",
            batch.id,
            user_id,
            station_id,
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "event": "MATERIAL_TAG_BATCH_ISSUED",
                "material_code": batch.material_code_snapshot,
                "vendor_lot": batch.vendor_lot,
                "tag_count": batch.tag_count,
                "total_weight": f"{batch.total_received_weight:.3f}",
            },
        )
        db.session.commit()
        return batch
    except MaterialTagIssuanceError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        existing = db.session.scalar(
            select(MaterialTagBatch).where(MaterialTagBatch.source_draft_token == token)
        )
        if existing is not None:
            return existing
        if _collision_attempt + 1 < MAX_BATCH_NUMBER_ATTEMPTS:
            return issue_material_tag_draft(
                token=token,
                user_id=user_id,
                station_id=station_id,
                _collision_attempt=_collision_attempt + 1,
            )
        raise MaterialTagIssuanceError(
            "Material Tag issuance failed safely; no records were issued."
        ) from exc
    except Exception as exc:
        db.session.rollback()
        raise MaterialTagIssuanceError(
            "Material Tag issuance failed safely; no records were issued."
        ) from exc


def material_tag_qr_data_uri(payload):
    parsed = parse_material_tag(payload)
    if parsed.raw_payload != payload:
        raise MaterialTagIssuanceError("Stored Material Tag QR payload is invalid.")
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=6, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _reprint_reason(value):
    normalized = unicodedata.normalize("NFC", str(value or "")).strip()
    if not 10 <= len(normalized) <= 500:
        raise MaterialTagIssuanceError("Reprint reason must contain 10 to 500 characters.")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise MaterialTagIssuanceError("Reprint reason must not contain control characters.")
    return normalized


def create_print_event(
    *, batch_id, user_id, station_id, print_type, scope="BATCH", tag_id=None, reason=None
):
    batch = db.session.get(MaterialTagBatch, batch_id)
    if batch is None:
        raise MaterialTagIssuanceError("Issued Material Tag batch was not found.")
    if len(batch.material_name_snapshot) > MAX_PRINTABLE_MATERIAL_NAME:
        raise MaterialTagIssuanceError(
            "Material Name is too long for a readable 3 x 2.5 inch label."
        )
    material_tag = None
    if scope == "INDIVIDUAL":
        material_tag = db.session.get(MaterialTag, tag_id)
        if material_tag is None or material_tag.batch_id != batch.id:
            raise MaterialTagIssuanceError("Selected Material Tag does not belong to this batch.")
    if print_type == "ORIGINAL":
        if scope != "BATCH" or reason:
            raise MaterialTagIssuanceError("Original printing must render the complete batch.")
        existing = db.session.scalar(
            select(MaterialTagPrintEvent).where(
                MaterialTagPrintEvent.batch_id == batch.id,
                MaterialTagPrintEvent.print_type == "ORIGINAL",
                MaterialTagPrintEvent.result == "RENDERED",
            )
        )
        if existing is not None:
            return existing
    elif print_type == "REPRINT":
        reason = _reprint_reason(reason)
    else:
        raise MaterialTagIssuanceError("Unknown print intent.")
    try:
        material_tag_qr_data_uri(batch.qr_payload)
    except Exception as exc:
        db.session.rollback()
        failed = MaterialTagPrintEvent(
            batch_id=batch.id,
            material_tag_id=material_tag.id if material_tag else None,
            print_scope=scope,
            print_type=print_type,
            result="FAILED",
            reason=reason,
            requested_by_user_id=user_id,
            requested_at_utc=utcnow(),
            printer_name=None,
            error_message="Stored QR payload could not be rendered.",
        )
        db.session.add(failed)
        db.session.flush()
        _audit(
            "MATERIAL_TAG_PRINT_FAILED",
            "MATERIAL_TAG_PRINT_EVENT",
            failed.id,
            user_id,
            station_id,
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "material_code": batch.material_code_snapshot,
                "print_event_id": failed.id,
                "scope": scope,
                "sequence": material_tag.sequence_no if material_tag else None,
                "result": "FAILED",
            },
        )
        db.session.commit()
        raise MaterialTagIssuanceError("Print page rendering failed safely.") from exc
    try:
        event = MaterialTagPrintEvent(
            batch_id=batch.id,
            material_tag_id=material_tag.id if material_tag else None,
            print_scope=scope,
            print_type=print_type,
            result="RENDERED",
            reason=reason,
            requested_by_user_id=user_id,
            requested_at_utc=utcnow(),
            printer_name=None,
            error_message=None,
        )
        db.session.add(event)
        db.session.flush()
        audit_type = (
            "MATERIAL_TAG_BATCH_PRINT_RENDERED"
            if print_type == "ORIGINAL"
            else "MATERIAL_TAG_REPRINT_RENDERED"
        )
        _audit(
            audit_type,
            "MATERIAL_TAG_PRINT_EVENT",
            event.id,
            user_id,
            station_id,
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "material_code": batch.material_code_snapshot,
                "print_event_id": event.id,
                "scope": scope,
                "sequence": material_tag.sequence_no if material_tag else None,
                "result": event.result,
            },
        )
        db.session.commit()
        return event
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, MaterialTagIssuanceError):
            raise
        raise MaterialTagIssuanceError("Print page rendering failed safely.") from exc
