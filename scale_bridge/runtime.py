import time
from threading import Event

from .ids701 import IDS701StreamParser
from .serial_source import SerialSourceError


class ScaleBridgeRuntime:
    def __init__(
        self,
        source,
        engine,
        identity,
        *,
        reconnect_interval=2.0,
        sleep=time.sleep,
        logger=None,
    ):
        self.source = source
        self.engine = engine
        self.identity = identity
        self.parser = IDS701StreamParser()
        self.reconnect_interval = reconnect_interval
        self.sleep = sleep
        self.logger = logger

    def run(self, stop_event: Event):
        while not stop_event.is_set():
            try:
                if not self.source.connected:
                    self.source.open()
                    self.parser.reset()
                    self.identity = self.identity.with_port(self.source.config.port)
                    self.engine.begin_connection(self.identity)
                chunk = self.source.read()
                for result in self.parser.feed(chunk):
                    self.engine.ingest(result)
            except SerialSourceError as exc:
                self.source.close()
                self.engine.disconnect(exc.code)
                if self.logger:
                    self.logger.warning("Scale connection state: %s", exc.code)
                stop_event.wait(self.reconnect_interval)

    def close(self):
        self.source.close()
        self.engine.disconnect()
