import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

FRAME_TERMINATOR = b"\r\n"
FRAME_PATTERN = re.compile(
    r"^(?P<status>ST|US|OL),(?P<mode>GS|NT),(?P<sign>[+-])\s*"
    r"(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)$"
)
SUPPORTED_UNITS = frozenset({"kg", "g", "lb"})


@dataclass(frozen=True, slots=True)
class ParseResult:
    decode_status: str
    raw_frame: bytes
    status: str | None = None
    mode: str | None = None
    weight: Decimal | None = None
    unit: str | None = None
    reason: str | None = None

    @property
    def decoded(self):
        return self.decode_status == "DECODED"

    @property
    def stable(self):
        return self.decoded and self.status == "ST"

    @property
    def overload(self):
        return self.decoded and self.status == "OL"

    def as_dict(self):
        return {
            "decode_status": self.decode_status,
            "status": self.status,
            "mode": self.mode,
            "weight": str(self.weight) if self.weight is not None else None,
            "unit": self.unit,
            "reason": self.reason,
            "raw_frame_hex": self.raw_frame.hex(),
        }


class IDS701FrameParser:
    def parse(self, raw_frame: bytes) -> ParseResult:
        evidence = bytes(raw_frame)
        try:
            frame = evidence.decode("ascii")
        except UnicodeDecodeError:
            return self._not_decoded(evidence, "INVALID_ASCII")

        fields = frame.split(",", 2)
        if len(fields) != 3:
            return self._not_decoded(evidence, "MALFORMED_FRAME")
        if fields[0] not in {"ST", "US", "OL"}:
            return self._not_decoded(evidence, "UNKNOWN_STATUS")
        if fields[1] not in {"GS", "NT"}:
            return self._not_decoded(evidence, "UNKNOWN_MODE")

        match = FRAME_PATTERN.fullmatch(frame)
        if match is None:
            return self._not_decoded(evidence, "MALFORMED_FRAME")

        unit = match.group("unit")
        if unit not in SUPPORTED_UNITS:
            return self._not_decoded(evidence, "UNKNOWN_UNIT")
        try:
            weight = Decimal(f"{match.group('sign')}{match.group('weight')}")
        except InvalidOperation:
            return self._not_decoded(evidence, "INVALID_WEIGHT")
        return ParseResult(
            decode_status="DECODED",
            raw_frame=evidence,
            status=match.group("status"),
            mode=match.group("mode"),
            weight=weight,
            unit=unit,
        )

    @staticmethod
    def _not_decoded(raw_frame: bytes, reason: str):
        return ParseResult(
            decode_status="NOT_DECODED",
            raw_frame=raw_frame,
            reason=reason,
        )


class IDS701StreamParser:
    def __init__(self, *, max_frame_bytes: int = 256):
        self._buffer = bytearray()
        self._frame_parser = IDS701FrameParser()
        self._max_frame_bytes = max_frame_bytes

    def feed(self, chunk: bytes) -> list[ParseResult]:
        if not isinstance(chunk, bytes):
            raise TypeError("serial chunks must be bytes")
        self._buffer.extend(chunk)
        results = []
        while FRAME_TERMINATOR in self._buffer:
            frame, _, remaining = self._buffer.partition(FRAME_TERMINATOR)
            self._buffer = bytearray(remaining)
            results.append(self._frame_parser.parse(bytes(frame)))
        if len(self._buffer) > self._max_frame_bytes:
            evidence = bytes(self._buffer[: self._max_frame_bytes])
            self._buffer.clear()
            results.append(
                ParseResult(
                    decode_status="NOT_DECODED",
                    raw_frame=evidence,
                    reason="FRAME_TOO_LONG",
                )
            )
        return results

    def reset(self):
        self._buffer.clear()
