import calendar
import json
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from app.services.weighing import MaterialTagError, parse_material_tag

WEIGHT_QUANTUM = Decimal("0.001")
DEFAULT_MAXIMUM_TAGS = 200


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
