from collections.abc import Callable
from dataclasses import dataclass, replace

from .identity import ScaleIdentity


class SerialSourceError(RuntimeError):
    code = "SERIAL_ERROR"


class PortMissingError(SerialSourceError):
    code = "PORT_MISSING"


class PortBusyError(SerialSourceError):
    code = "PORT_BUSY"


class ScaleDisconnectedError(SerialSourceError):
    code = "DISCONNECTED"


@dataclass(frozen=True, slots=True)
class SerialConfig:
    port: str = "COM3"
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    timeout: float = 0.5
    xonxoff: bool = False
    rtscts: bool = False
    dsrdtr: bool = False


@dataclass(frozen=True, slots=True)
class DiscoveredPort:
    device: str
    vid: int | None
    pid: int | None
    serial_number: str | None
    description: str | None


def discover_ports(
    *,
    vid: int = 0x0403,
    pid: int = 0x6001,
    usb_serial_number: str | None = None,
    list_ports_provider: Callable | None = None,
):
    if list_ports_provider is None:
        try:
            from serial.tools import list_ports
        except ImportError as exc:
            raise SerialSourceError("pyserial is required for serial discovery") from exc
        list_ports_provider = list_ports.comports
    matches = []
    for port in list_ports_provider():
        if port.vid != vid or port.pid != pid:
            continue
        if usb_serial_number and port.serial_number != usb_serial_number:
            continue
        matches.append(
            DiscoveredPort(
                device=port.device,
                vid=port.vid,
                pid=port.pid,
                serial_number=port.serial_number,
                description=port.description,
            )
        )
    return matches


def resolve_port(identity: ScaleIdentity, configured_port: str | None = None, **kwargs):
    matches = discover_ports(
        vid=identity.vid,
        pid=identity.pid,
        usb_serial_number=identity.usb_serial_number,
        **kwargs,
    )
    if identity.usb_serial_number and len(matches) == 1:
        return matches[0].device
    if configured_port:
        return configured_port
    if len(matches) == 1:
        return matches[0].device
    raise PortMissingError("configured scale port is unavailable or ambiguous")


class ReadOnlySerialSource:
    """Receive-only serial transport. This class intentionally exposes no send operation."""

    def __init__(self, config: SerialConfig, *, serial_factory=None, port_resolver=None):
        self.config = config
        self._serial_factory = serial_factory
        self._port_resolver = port_resolver
        self._connection = None
        self._read_errors = (OSError,)

    @property
    def connected(self):
        return bool(self._connection and getattr(self._connection, "is_open", True))

    def open(self):
        if self.connected:
            return
        if self._port_resolver is not None:
            self.config = replace(self.config, port=self._port_resolver())
        factory = self._serial_factory
        serial_exception = OSError
        if factory is None:
            try:
                import serial
            except ImportError as exc:
                raise SerialSourceError("pyserial is required for serial communication") from exc
            factory = serial.Serial
            serial_exception = serial.SerialException
            self._read_errors = (OSError, serial.SerialException)
        try:
            self._connection = factory(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                timeout=self.config.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except (serial_exception, OSError) as exc:
            message = str(exc).lower()
            if "access" in message or "busy" in message or "permission" in message:
                raise PortBusyError("serial port is already in use") from exc
            raise PortMissingError("serial port is unavailable") from exc

    def read(self, size: int = 256):
        if not self.connected:
            raise ScaleDisconnectedError("scale is disconnected")
        try:
            return self._connection.read(size)
        except self._read_errors as exc:
            self.close()
            raise ScaleDisconnectedError("scale disconnected while reading") from exc

    def close(self):
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.close()

    def reconnect(self):
        self.close()
        self.open()
