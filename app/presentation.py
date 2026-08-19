from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def format_local_datetime(value: datetime | None, timezone_name: str) -> str:
    """Format the project's timezone-naive UTC storage for operator display."""
    if value is None:
        return "—"
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    local_value = utc_value.astimezone(ZoneInfo(timezone_name))
    zone_label = "Thailand Time" if timezone_name == "Asia/Bangkok" else timezone_name
    return f"{local_value:%d/%m/%Y %H:%M:%S} ({zone_label})"


def format_local_date(value: date | None) -> str:
    """Format an application date using the operator-facing convention."""
    return "—" if value is None else value.strftime("%d/%m/%Y")


def parse_user_date(value, *, required=True) -> date | None:
    """Parse a strict, unambiguous operator-entered dd/mm/yyyy date."""
    if type(value) is date:
        return value
    raw = "" if value is None else str(value).strip()
    if not raw:
        if required:
            raise ValueError("Date is required. Use dd/mm/yyyy.")
        return None
    try:
        parsed = datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError("Enter a valid date in dd/mm/yyyy format.") from exc
    if parsed.strftime("%d/%m/%Y") != raw:
        raise ValueError("Enter a valid date in dd/mm/yyyy format.")
    return parsed
