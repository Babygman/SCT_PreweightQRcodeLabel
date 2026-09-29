from decimal import Decimal

import pytest

from scale_bridge.ids701 import IDS701FrameParser, IDS701StreamParser


@pytest.mark.parametrize(
    ("frame", "status", "mode", "weight", "unit"),
    [
        (b"ST,GS,+   0.00kg", "ST", "GS", Decimal("0.00"), "kg"),
        (b"ST,GS,+   0.08kg", "ST", "GS", Decimal("0.08"), "kg"),
        (b"US,GS,+   3.82kg", "US", "GS", Decimal("3.82"), "kg"),
        (b"ST,GS,-   0.08kg", "ST", "GS", Decimal("-0.08"), "kg"),
        (b"OL,GS,+99999.99kg", "OL", "GS", Decimal("99999.99"), "kg"),
        (b"ST,NT,+   2.00kg", "ST", "NT", Decimal("2.00"), "kg"),
        (b"ST,GS,+ 1000.00g", "ST", "GS", Decimal("1000.00"), "g"),
    ],
)
def test_valid_frames_use_decimal(frame, status, mode, weight, unit):
    result = IDS701FrameParser().parse(frame)
    assert result.decoded
    assert (result.status, result.mode, result.weight, result.unit) == (
        status,
        mode,
        weight,
        unit,
    )


@pytest.mark.parametrize(
    ("frame", "reason"),
    [
        (b"\xff\xfe", "INVALID_ASCII"),
        (b"BROKEN", "MALFORMED_FRAME"),
        (b"XX,GS,+ 1.00kg", "UNKNOWN_STATUS"),
        (b"ST,XX,+ 1.00kg", "UNKNOWN_MODE"),
        (b"ST,GS,+ 1.00oz", "UNKNOWN_UNIT"),
        (b"", "MALFORMED_FRAME"),
    ],
)
def test_invalid_frames_are_explicitly_not_decoded_and_never_zero(frame, reason):
    result = IDS701FrameParser().parse(frame)
    assert result.decode_status == "NOT_DECODED"
    assert result.reason == reason
    assert result.weight is None
    assert result.raw_frame == frame


def test_fragmented_and_combined_crlf_frames():
    parser = IDS701StreamParser()
    assert parser.feed(b"ST,GS,+   0.") == []
    results = parser.feed(b"08kg\r\nUS,GS,+   3.82kg\r\n")
    assert [result.weight for result in results] == [Decimal("0.08"), Decimal("3.82")]
    assert [result.status for result in results] == ["ST", "US"]


def test_overlong_partial_frame_is_not_decoded_and_buffer_is_reset():
    parser = IDS701StreamParser(max_frame_bytes=8)
    result = parser.feed(b"0123456789").pop()
    assert result.decode_status == "NOT_DECODED"
    assert result.reason == "FRAME_TOO_LONG"
    assert parser.feed(b"ST,GS,+0.00kg\r\n")[0].weight == Decimal("0.00")
