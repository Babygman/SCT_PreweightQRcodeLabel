import argparse
import socket
from threading import Event, Thread

from .api import create_server
from .identity import ScaleIdentity
from .runtime import ScaleBridgeRuntime
from .serial_source import ReadOnlySerialSource, SerialConfig, resolve_port
from .state import ScaleStateEngine


def main():
    parser = argparse.ArgumentParser(description="Receive-only IDS701 Scale Bridge prototype")
    parser.add_argument("--scale-code", required=True)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--usb-serial")
    parser.add_argument("--origin", action="append", required=True)
    parser.add_argument("--api-port", type=int, default=8765)
    parser.add_argument("--stale-seconds", type=float, default=2.0)
    args = parser.parse_args()

    identity = ScaleIdentity(
        scale_code=args.scale_code,
        usb_serial_number=args.usb_serial,
        com_port=args.port,
        workstation=socket.gethostname(),
    )
    source = ReadOnlySerialSource(
        SerialConfig(port=args.port),
        port_resolver=lambda: resolve_port(identity, configured_port=args.port),
    )
    engine = ScaleStateEngine(stale_after_seconds=args.stale_seconds)
    runtime = ScaleBridgeRuntime(source, engine, identity)
    server = create_server(engine, port=args.api_port, allowed_origins=args.origin)
    stop = Event()
    reader = Thread(target=runtime.run, args=(stop,), daemon=True)
    reader.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        runtime.close()
        server.shutdown()
        server.server_close()
        reader.join(timeout=3)


if __name__ == "__main__":
    main()
