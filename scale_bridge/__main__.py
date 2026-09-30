import argparse
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config
from .host import BridgeHost


def main():
    parser = argparse.ArgumentParser(description="Receive-only IDS701 Scale Bridge")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--log-dir", type=Path)
    args = parser.parse_args()

    config = load_config(args.config)
    log_dir = args.log_dir or args.config.parent / "logs"
    host = BridgeHost(config, log_dir)
    try:
        host.serve()
    except KeyboardInterrupt:
        host.stop()


if __name__ == "__main__":
    main()
