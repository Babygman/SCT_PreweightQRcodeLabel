from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from scale_bridge.identity import ScaleIdentity
from scale_bridge.ids701 import IDS701FrameParser
from scale_bridge.state import ScaleStateEngine, ScaleStateError, WeighingContext


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)

    def __call__(self):
        return self.now


def reading(frame):
    return IDS701FrameParser().parse(frame)


def connected_engine():
    clock = Clock()
    engine = ScaleStateEngine(stale_after_seconds=2, clock=clock)
    identity = ScaleIdentity(
        scale_code="SCALE-01",
        usb_serial_number="FT-ABC",
        com_port="COM3",
        workstation="WEIGH-01",
    )
    engine.connect(identity)
    engine.set_context(
        WeighingContext("R01006S1", "PO-1", "LINE-1", "ST-1", "SCALE-01")
    )
    return engine, clock


def test_software_tare_and_decimal_actual_weight():
    engine, clock = connected_engine()
    engine.ingest(reading(b"ST,GS,+   0.80kg"), received_at=clock())
    assert engine.capture_tare() == Decimal("0.80")
    engine.ingest(reading(b"ST,GS,+   3.82kg"), received_at=clock())
    state = engine.snapshot()
    assert state["gross"] == "3.82"
    assert state["tare"] == "0.80"
    assert state["actual"] == "3.02"
    assert state["save_eligible"] is True
    assert state["save_block_reason"] is None


@pytest.mark.parametrize(
    ("frame", "reason"),
    [
        (b"US,GS,+   0.80kg", "READING_UNSTABLE"),
        (b"OL,GS,+99999.99kg", "OVERLOAD"),
        (b"ST,NT,+   0.80kg", "GROSS_MODE_REQUIRED"),
        (b"ST,GS,+ 800.00g", "KG_REQUIRED"),
        (b"BROKEN", "NOT_DECODED"),
    ],
)
def test_tare_rejects_invalid_reading_states(frame, reason):
    engine, clock = connected_engine()
    engine.ingest(reading(frame), received_at=clock())
    with pytest.raises(ScaleStateError, match=reason):
        engine.capture_tare()
    assert engine.tare_weight is None


def test_tare_rejects_missing_stale_and_disconnected_readings():
    engine, clock = connected_engine()
    with pytest.raises(ScaleStateError, match="READING_MISSING"):
        engine.capture_tare()
    engine.ingest(reading(b"ST,GS,+   0.80kg"), received_at=clock())
    clock.now += timedelta(seconds=3)
    with pytest.raises(ScaleStateError, match="READING_STALE"):
        engine.capture_tare()
    engine.disconnect()
    with pytest.raises(ScaleStateError, match="DISCONNECTED"):
        engine.capture_tare()


@pytest.mark.parametrize(
    "replacement",
    [
        WeighingContext("MAT-2", "PO-1", "LINE-1", "ST-1", "SCALE-01"),
        WeighingContext("MAT-1", "PO-2", "LINE-1", "ST-1", "SCALE-01"),
        WeighingContext("MAT-1", "PO-1", "LINE-2", "ST-1", "SCALE-01"),
        WeighingContext("MAT-1", "PO-1", "LINE-1", "ST-2", "SCALE-01"),
        WeighingContext("MAT-1", "PO-1", "LINE-1", "ST-1", "SCALE-02"),
    ],
)
def test_every_work_context_change_clears_tare(replacement):
    engine, clock = connected_engine()
    engine.ingest(reading(b"ST,GS,+   0.80kg"), received_at=clock())
    engine.capture_tare()
    engine.set_context(replacement)
    assert engine.tare_weight is None
    assert engine.snapshot()["save_block_reason"] == "TARE_MISSING"


def test_reconnect_changes_session_and_never_reuses_tare():
    engine, clock = connected_engine()
    engine.ingest(reading(b"ST,GS,+   0.80kg"), received_at=clock())
    engine.capture_tare()
    session = engine.snapshot()["session_number"]
    identity = engine.identity.with_port("COM7", "WEIGH-02")
    engine.disconnect()
    engine.connect(identity)
    state = engine.snapshot()
    assert state["session_number"] == session + 1
    assert state["tare"] is None
    assert state["reading"] is None
    assert state["save_block_reason"] == "READING_MISSING"
    assert state["scale_identity"]["com_port"] == "COM7"
    assert state["workstation"] == "WEIGH-02"


def test_non_positive_actual_weight_blocks_save():
    engine, clock = connected_engine()
    engine.ingest(reading(b"ST,GS,+   1.00kg"), received_at=clock())
    engine.capture_tare()
    engine.ingest(reading(b"ST,GS,+   0.90kg"), received_at=clock())
    assert engine.snapshot()["save_block_reason"] == "ACTUAL_WEIGHT_NOT_POSITIVE"
