import os
import pty
import time
from decimal import Decimal


class MemoryTransport:
    def __init__(self):
        self.chunks = []
        self.connected = True

    def emit(self, data: bytes):
        if not self.connected:
            raise ConnectionError("simulator is disconnected")
        self.chunks.append(data)

    def disconnect(self):
        self.connected = False

    def reconnect(self):
        self.connected = True


class PseudoTerminalTransport:
    def __init__(self):
        self.master_fd = None
        self.slave_fd = None
        self.device = None
        self.reconnect()

    def emit(self, data: bytes):
        if self.master_fd is None:
            raise ConnectionError("simulator is disconnected")
        os.write(self.master_fd, data)

    def disconnect(self):
        for descriptor in (self.master_fd, self.slave_fd):
            if descriptor is not None:
                os.close(descriptor)
        self.master_fd = self.slave_fd = self.device = None

    def reconnect(self):
        self.disconnect()
        self.master_fd, self.slave_fd = pty.openpty()
        self.device = os.ttyname(self.slave_fd)


class IDS701Simulator:
    def __init__(self, transport, *, interval=0.5):
        self.transport = transport
        self.interval = interval

    @staticmethod
    def frame(status="ST", mode="GS", weight="0.00", unit="kg"):
        value = Decimal(str(weight))
        sign = "+" if value >= 0 else "-"
        magnitude = f"{abs(value):7.2f}"
        return f"{status},{mode},{sign}{magnitude}{unit}\r\n".encode("ascii")

    def stable_zero(self):
        self.transport.emit(self.frame(weight="0.00"))

    def stable_gross(self, weight):
        self.transport.emit(self.frame(weight=weight))

    def unstable_gross(self, weight):
        self.transport.emit(self.frame(status="US", weight=weight))

    def negative(self, weight="-0.08"):
        self.transport.emit(self.frame(weight=weight))

    def overload(self):
        self.transport.emit(self.frame(status="OL", weight="99999.99"))

    def net_mode(self, weight):
        self.transport.emit(self.frame(mode="NT", weight=weight))

    def malformed(self):
        self.transport.emit(b"BROKEN IDS701 FRAME\r\n")

    def partial(self, weight="3.82"):
        frame = self.frame(weight=weight)
        midpoint = len(frame) // 2
        self.transport.emit(frame[:midpoint])
        self.transport.emit(frame[midpoint:])

    def multiple(self, *weights):
        self.transport.emit(b"".join(self.frame(weight=weight) for weight in weights))

    def disconnect(self):
        self.transport.disconnect()

    def reconnect(self):
        self.transport.reconnect()

    def stream(self, frames, *, repeat=1):
        for _ in range(repeat):
            for frame in frames:
                self.transport.emit(frame)
                time.sleep(self.interval)
