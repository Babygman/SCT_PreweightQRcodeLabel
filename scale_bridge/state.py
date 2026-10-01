from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from .identity import ScaleIdentity
from .ids701 import ParseResult


@dataclass(frozen=True, slots=True)
class WeighingContext:
    material: str | None = None
    production_order: str | None = None
    formula_item: str | None = None
    station: str | None = None
    scale: str | None = None
    workflow_attempt: str | None = None


class ScaleStateError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ScaleStateEngine:
    def __init__(self, *, stale_after_seconds=2, clock=None):
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.connected = False
        self.connection_reason = "DISCONNECTED"
        self.identity: ScaleIdentity | None = None
        self.context = WeighingContext()
        self.latest: ParseResult | None = None
        self.last_reading_at: datetime | None = None
        self.tare_weight: Decimal | None = None
        self._session_number = 0

    def connect(self, identity: ScaleIdentity):
        self.begin_connection(identity)
        self.connected = True
        self.connection_reason = None

    def begin_connection(self, identity: ScaleIdentity):
        self.connected = False
        self.connection_reason = "READING_MISSING"
        self.identity = identity
        self._session_number += 1
        self.latest = None
        self.last_reading_at = None
        self._clear_for_boundary()

    def disconnect(self, reason="DISCONNECTED"):
        self.connected = False
        self.connection_reason = reason
        self.latest = None
        self.last_reading_at = None
        self._clear_for_boundary()

    def ingest(self, reading: ParseResult, *, received_at=None):
        self.latest = reading
        self.last_reading_at = received_at or self.clock()
        if reading.decoded:
            self.connected = True
            self.connection_reason = None

    def set_context(self, context: WeighingContext):
        if context != self.context:
            self.context = context
            self.clear_tare()

    def clear_tare(self):
        self.tare_weight = None

    def capture_tare(self):
        if self.tare_weight is not None:
            raise ScaleStateError("TARE_ALREADY_CAPTURED")
        reason = self._tare_block_reason()
        if reason:
            raise ScaleStateError(reason)
        self.tare_weight = self.latest.weight
        return self.tare_weight

    @property
    def actual_weight(self):
        if self.tare_weight is None or not self.latest or self.latest.weight is None:
            return None
        return self.latest.weight - self.tare_weight

    @property
    def stale(self):
        return (
            self.last_reading_at is None
            or self.clock() - self.last_reading_at > self.stale_after
        )

    def save_block_reason(self):
        common = self._reading_block_reason(require_gross=True)
        if common:
            return common
        if self.tare_weight is None:
            return "TARE_MISSING"
        if self.actual_weight <= 0:
            return "ACTUAL_WEIGHT_NOT_POSITIVE"
        return None

    def snapshot(self):
        reading = self.latest
        reason = self.save_block_reason()
        return {
            "connected": self.connected,
            "connection_reason": self.connection_reason,
            "stable": bool(reading and reading.stable),
            "overload": bool(reading and reading.overload),
            "gross": self._decimal(reading.weight if reading else None),
            "tare": self._decimal(self.tare_weight),
            "actual": self._decimal(self.actual_weight),
            "net": self._decimal(self.actual_weight),
            "unit": reading.unit if reading else None,
            "last_reading_time": self.last_reading_at.isoformat() if self.last_reading_at else None,
            "scale_identity": self.identity.as_dict() if self.identity else None,
            "workstation": self.identity.workstation if self.identity else None,
            "context": asdict(self.context),
            "save_eligible": reason is None,
            "save_block_reason": reason,
            "session_number": self._session_number,
            "reading": reading.as_dict() if reading else None,
        }

    def _tare_block_reason(self):
        return self._reading_block_reason(require_gross=True)

    def _reading_block_reason(self, *, require_gross):
        if not self.connected:
            return "DISCONNECTED"
        if self.latest is None:
            return "READING_MISSING"
        if not self.latest.decoded:
            return "NOT_DECODED"
        if self.stale:
            return "READING_STALE"
        if self.latest.status == "OL":
            return "OVERLOAD"
        if self.latest.status != "ST":
            return "READING_UNSTABLE"
        if require_gross and self.latest.mode != "GS":
            return "GROSS_MODE_REQUIRED"
        if self.latest.unit != "kg":
            return "KG_REQUIRED"
        return None

    def _clear_for_boundary(self):
        self.clear_tare()

    @staticmethod
    def _decimal(value):
        return str(value) if value is not None else None
