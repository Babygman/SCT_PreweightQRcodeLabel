import json
import os
import re
import stat
from dataclasses import asdict, dataclass, fields
from ipaddress import ip_address
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

DEFAULT_CONFIG_DIR = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SCT" / "ScaleBridge"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


class ConfigurationError(ValueError):
    pass


_HOST_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def validate_origin(origin):
    if not isinstance(origin, str) or not origin or origin != origin.strip() or "*" in origin:
        raise ConfigurationError(f"invalid approved Origin: {origin!r}")
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(f"invalid approved Origin: {origin!r}") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(f"invalid approved Origin: {origin!r}")
    hostname = parsed.hostname
    if not hostname or hostname.endswith(".") or any(character.isspace() for character in hostname):
        raise ConfigurationError(f"invalid approved Origin: {origin!r}")
    try:
        ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ConfigurationError(f"invalid approved Origin: {origin!r}") from exc
        if len(ascii_hostname) > 253 or any(
            not _HOST_LABEL.fullmatch(label) for label in ascii_hostname.split(".")
        ):
            raise ConfigurationError(f"invalid approved Origin: {origin!r}") from None
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError(f"invalid approved Origin: {origin!r}")
    return origin


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
            validate_origin(origin)
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
    payload = json.dumps(config.as_json_dict(), indent=2, ensure_ascii=False) + "\n"
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if target.exists():
            _copy_existing_permissions(target, temporary)
        temporary.replace(target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _copy_existing_permissions(existing, temporary, *, platform_name=None, windows_security=None):
    platform_name = platform_name or os.name
    if platform_name == "nt":
        if windows_security is None:
            import win32security as windows_security

        security_information = windows_security.DACL_SECURITY_INFORMATION
        descriptor = windows_security.GetFileSecurity(str(existing), security_information)
        windows_security.SetFileSecurity(str(temporary), security_information, descriptor)
        return
    temporary.chmod(stat.S_IMODE(existing.stat().st_mode))
