import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_CONFIG_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SCT" / "ScaleBridge"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    workstation_code: str
    scale_code: str
    allowed_origins: tuple[str, ...]
    preferred_usb_serial: str | None = None
    vid: int = 0x0403
    pid: int = 0x6001
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    xonxoff: bool = False
    rtscts: bool = False
    dsrdtr: bool = False
    api_port: int = 8765
    stale_seconds: float = 2.0

    def validate(self):
        if not self.workstation_code.strip() or not self.scale_code.strip():
            raise ConfigurationError("workstation_code and scale_code are required")
        if not self.allowed_origins:
            raise ConfigurationError("at least one approved Origin is required")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ConfigurationError(f"invalid approved Origin: {origin!r}")
            if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ConfigurationError("Origins must not include paths, queries, or fragments")
        if (self.vid, self.pid) != (0x0403, 0x6001):
            raise ConfigurationError("only the approved FTDI 0403:6001 adapter is supported")
        if (self.baudrate, self.bytesize, self.parity, self.stopbits) != (9600, 8, "N", 1):
            raise ConfigurationError("IDS701 serial settings must be 9600/8N1")
        if self.xonxoff or self.rtscts or self.dsrdtr:
            raise ConfigurationError("serial flow control must remain disabled")
        if not 1024 <= self.api_port <= 65535:
            raise ConfigurationError("api_port must be between 1024 and 65535")
        if self.stale_seconds <= 0:
            raise ConfigurationError("stale_seconds must be positive")
        return self

    def as_json_dict(self):
        data = asdict(self)
        data["allowed_origins"] = list(self.allowed_origins)
        data["vid"] = f"{self.vid:04X}"
        data["pid"] = f"{self.pid:04X}"
        return data


def load_config(path=DEFAULT_CONFIG_PATH):
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"configuration could not be loaded: {config_path}") from exc
    allowed = {item.name for item in fields(BridgeConfig)}
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigurationError(f"unknown configuration fields: {sorted(unknown)}")
    raw["allowed_origins"] = tuple(raw.get("allowed_origins", ()))
    for key in ("vid", "pid"):
        if isinstance(raw.get(key), str):
            raw[key] = int(raw[key], 16)
    try:
        return BridgeConfig(**raw).validate()
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError("configuration values are invalid") from exc


def save_config(config: BridgeConfig, path=DEFAULT_CONFIG_PATH):
    config.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.as_json_dict(), indent=2) + "\n"
    if target.exists():
        # Overwriting the existing file preserves its installer-managed Windows ACL.
        target.write_text(payload, encoding="utf-8")
        return
    temporary = target.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
