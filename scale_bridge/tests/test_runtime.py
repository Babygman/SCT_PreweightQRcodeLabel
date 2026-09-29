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
        self.config = SerialConfig()

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
