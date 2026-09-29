import argparse
import time

from .simulator import IDS701Simulator, PseudoTerminalTransport


def main():
    parser = argparse.ArgumentParser(description="macOS IDS701 pseudo-terminal simulator")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--tare-weight", default="0.80")
    parser.add_argument("--gross-weight", default="3.82")
    args = parser.parse_args()

    transport = PseudoTerminalTransport()
    simulator = IDS701Simulator(transport, interval=args.interval)
    print(f"Simulator serial device: {transport.device}")
    print("Press Ctrl+C to stop. Frames: zero, container, material, unstable, stable.")
    try:
        while True:
            simulator.stable_zero()
            time.sleep(args.interval)
            simulator.stable_gross(args.tare_weight)
            time.sleep(args.interval)
            simulator.stable_gross(args.gross_weight)
            time.sleep(args.interval)
            simulator.unstable_gross(args.gross_weight)
            time.sleep(args.interval)
            simulator.stable_gross(args.gross_weight)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        transport.disconnect()


if __name__ == "__main__":
    main()
