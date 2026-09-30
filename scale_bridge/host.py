from pathlib import Path
from threading import Event, Thread

from .api import create_server
from .config import BridgeConfig
from .identity import ScaleIdentity
from .logging_setup import configure_logging
from .runtime import ScaleBridgeRuntime
from .serial_source import ReadOnlySerialSource, SerialConfig, resolve_port
from .state import ScaleStateEngine


class BridgeHost:
    def __init__(self, config: BridgeConfig, log_dir: Path):
        self.config = config.validate()
        self.log_dir = Path(log_dir)
        self.logger = configure_logging(self.log_dir)
        self.stop_event = Event()
        identity = ScaleIdentity(
            scale_code=self.config.scale_code,
            usb_serial_number=self.config.preferred_usb_serial,
            vid=self.config.vid,
            pid=self.config.pid,
            workstation=self.config.workstation_code,
        )
        source = ReadOnlySerialSource(
            SerialConfig(
                port=None,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            ),
            port_resolver=lambda: resolve_port(identity),
        )
        self.engine = ScaleStateEngine(stale_after_seconds=self.config.stale_seconds)
        self.runtime = ScaleBridgeRuntime(source, self.engine, identity, logger=self.logger)
        self.server = create_server(
            self.engine,
            port=self.config.api_port,
            allowed_origins=self.config.allowed_origins,
        )
        self.reader = Thread(target=self.runtime.run, args=(self.stop_event,), daemon=True)
        self._serving = False

    def serve(self):
        self.reader.start()
        self.logger.info("Scale Bridge started on loopback port %s", self.config.api_port)
        self._serving = True
        try:
            self.server.serve_forever()
        finally:
            self._serving = False
            self._cleanup()

    def stop(self):
        if self._serving:
            self.server.shutdown()
        else:
            self._cleanup()

    def _cleanup(self):
        self.stop_event.set()
        self.runtime.close()
        self.server.server_close()
        if self.reader.is_alive():
            self.reader.join(timeout=3)
