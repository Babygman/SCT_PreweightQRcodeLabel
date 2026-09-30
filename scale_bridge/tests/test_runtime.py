from threading import Event

from scale_bridge.identity import ScaleIdentity
from scale_bridge.runtime import ScaleBridgeRuntime
from scale_bridge.serial_source import PortMissingError, SerialConfig
from scale_bridge.state import ScaleStateEngine


class ScriptedSource:
    def __init__(self, script):
        self.script = iter(script)
        self.connected = False
        self.closed = 0
        self.config = SerialConfig(port="COM3")

    def open(self):
        self.connected = True

    def read(self, _size=256):
        value = next(self.script)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.connected = False
        self.closed += 1


def test_runtime_reads_frames_and_reports_controlled_disconnect():
    stop = Event()
    source = ScriptedSource(
        [b"ST,GS,+   0.80kg\r\n", PortMissingError("unplugged")]
    )
    engine = ScaleStateEngine()
    runtime = ScaleBridgeRuntime(
        source,
        engine,
        ScaleIdentity(scale_code="SCALE-01", com_port="COM3"),
        reconnect_interval=0,
    )

    class StopAfterDisconnect:
        def wait(self, _seconds):
            stop.set()
            return True

        def is_set(self):
            return stop.is_set()

    runtime.run(StopAfterDisconnect())
    assert engine.connected is False
    assert engine.connection_reason == "PORT_MISSING"
    assert source.closed == 1


def test_runtime_does_not_claim_connected_until_a_valid_frame_is_decoded():
    engine = ScaleStateEngine()
    source = ScriptedSource([b"BROKEN\r\n", b"ST,GS,+   1.00kg\r\n"])
    runtime = ScaleBridgeRuntime(
        source,
        engine,
        ScaleIdentity(scale_code="SCALE-01"),
        reconnect_interval=0,
    )
    source.open()
    runtime.identity = runtime.identity.with_port(source.config.port)
    engine.begin_connection(runtime.identity)
    for result in runtime.parser.feed(source.read()):
        engine.ingest(result)
    assert engine.connected is False
    assert engine.latest.decode_status == "NOT_DECODED"
    for result in runtime.parser.feed(source.read()):
        engine.ingest(result)
    assert engine.connected is True
    assert engine.latest.decoded is True
