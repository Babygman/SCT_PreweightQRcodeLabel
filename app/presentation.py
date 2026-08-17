from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def format_local_datetime(value: datetime | None, timezone_name: str) -> str:
    """Format the project's timezone-naive UTC storage for operator display."""
    if value is None:
        return "—"
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    local_value = utc_value.astimezone(ZoneInfo(timezone_name))
    zone_label = "Thailand Time" if timezone_name == "Asia/Bangkok" else timezone_name
    return f"{local_value:%d %b %Y %H:%M:%S} ({zone_label})"
