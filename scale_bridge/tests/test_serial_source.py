import inspect
from types import SimpleNamespace

import pytest

from scale_bridge.identity import ScaleIdentity
from scale_bridge.serial_source import (
    MultipleScalesError,
    PortBusyError,
    PortMissingError,
    ReadOnlySerialSource,
    SerialConfig,
    discover_ports,
    resolve_port,
)


class FakeConnection:
    is_open = True

    def __init__(self, **options):
        self.options = options
        self.closed = False

    def read(self, size):
        return b"ST,GS,+   0.00kg\r\n"[:size]

    def close(self):
        self.closed = True
        self.is_open = False


def test_serial_source_uses_9600_8n1_no_flow_control_and_reads_only():
    source = ReadOnlySerialSource(SerialConfig(port="COM3"), serial_factory=FakeConnection)
    source.open()
    assert source.read(64).endswith(b"\r\n")
    assert source._connection.options == {
        "port": "COM3",
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 0.5,
        "xonxoff": False,
        "rtscts": False,
        "dsrdtr": False,
    }
    assert not hasattr(source, "write")
    assert ".write(" not in inspect.getsource(ReadOnlySerialSource)


def test_port_busy_is_controlled_and_does_not_steal_port():
    def busy_factory(**_options):
        raise OSError("Access denied: port busy")

    source = ReadOnlySerialSource(SerialConfig(), serial_factory=busy_factory)
    with pytest.raises(PortBusyError, match="already in use"):
        source.open()
    assert not source.connected


def test_discovery_follows_ftdi_serial_and_manual_port_fallback():
    ports = [
        SimpleNamespace(
            device="COM7",
            vid=0x0403,
            pid=0x6001,
            serial_number="FT-ABC",
            description="FTDI FT232",
        ),
        SimpleNamespace(
            device="COM9",
            vid=0x0403,
            pid=0x6001,
            serial_number=None,
            description="FTDI FT232",
        ),
    ]
    def provider():
        return ports

    matches = discover_ports(list_ports_provider=provider)
    assert [match.device for match in matches] == ["COM7", "COM9"]
    identity = ScaleIdentity(scale_code="SCALE-01", usb_serial_number="FT-ABC")
    assert resolve_port(identity, list_ports_provider=provider) == "COM7"
    manual = ScaleIdentity(scale_code="SCALE-MANUAL", usb_serial_number=None)
    assert resolve_port(manual, configured_port="COM3", list_ports_provider=provider) == "COM3"


def test_automatic_discovery_handles_zero_one_multiple_and_preferred_devices():
    def port(device, serial):
        return SimpleNamespace(
            device=device,
            vid=0x0403,
            pid=0x6001,
            serial_number=serial,
            description="FTDI FT232",
        )

    identity = ScaleIdentity(scale_code="SCALE-01")
    with pytest.raises(PortMissingError, match="no eligible"):
        resolve_port(identity, list_ports_provider=lambda: [])
    assert resolve_port(identity, list_ports_provider=lambda: [port("COM7", "FT-A")]) == "COM7"
    with pytest.raises(MultipleScalesError, match="multiple eligible"):
        resolve_port(
            identity,
            list_ports_provider=lambda: [port("COM7", "FT-A"), port("COM9", "FT-B")],
        )
    preferred = ScaleIdentity(scale_code="SCALE-01", usb_serial_number="FT-B")
    assert (
        resolve_port(
            preferred,
            list_ports_provider=lambda: [port("COM7", "FT-A"), port("COM9", "FT-B")],
        )
        == "COM9"
    )
    with pytest.raises(PortMissingError, match="preferred scale"):
        resolve_port(preferred, list_ports_provider=lambda: [port("COM7", "FT-A")])


def test_reconnect_closes_previous_connection_and_reopens():
    connections = []
    assigned_ports = iter(["COM3", "COM7"])

    def factory(**options):
        connection = FakeConnection(**options)
        connections.append(connection)
        return connection

    source = ReadOnlySerialSource(
        SerialConfig(port=None),
        serial_factory=factory,
        port_resolver=lambda: next(assigned_ports),
    )
    source.open()
    source.reconnect()
    assert len(connections) == 2
    assert connections[0].closed
    assert connections[0].options["port"] == "COM3"
    assert connections[1].options["port"] == "COM7"
    assert source.connected
