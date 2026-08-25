import unicodedata

MAX_PRODUCTION_LOT_LENGTH = 100


class ProductionLotError(ValueError):
    """Raised when a Production Lot cannot form the approved business key."""


def normalize_production_lot(value):
    """Return the deterministic Product/Lot business-key representation."""
    if not isinstance(value, str):
        raise ProductionLotError("Production Lot must be a text value.")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ProductionLotError("Production Lot is required.")
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ProductionLotError("Production Lot must not contain control characters.")
    business_key = normalized.upper()
    if len(normalized) > MAX_PRODUCTION_LOT_LENGTH or len(business_key) > MAX_PRODUCTION_LOT_LENGTH:
        raise ProductionLotError(
            f"Production Lot must not exceed {MAX_PRODUCTION_LOT_LENGTH} characters."
        )
    return business_key


def clean_production_lot(value):
    """Validate a Lot and preserve its display value with outer whitespace removed."""
    normalize_production_lot(value)
    return value.strip()
