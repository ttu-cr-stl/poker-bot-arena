import argparse
import asyncio
import logging

from core.models import TableConfig
from .server import HostServer

logging.basicConfig(level=logging.INFO)


def main() -> None:
    # CLI doubles as documentation for common tournament toggles.
    parser = argparse.ArgumentParser(description="Poker Bot Arena host server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seats", type=int, default=6)
    parser.add_argument("--starting-stack", type=int, default=10_000)
    parser.add_argument("--sb", type=int, default=50)
    parser.add_argument("--bb", type=int, default=100)
    parser.add_argument(
        "--move-time",
        type=int,
        default=15_000,
        help="Move time in milliseconds (0 disables auto timeouts; requires manual skips)",
    )
    parser.add_argument(
        "--manual-control",
        action="store_true",
        help="Enable manual timeout control (equivalent to --move-time 0)",
    )
    parser.add_argument(
        "--presentation",
        action="store_true",
        help="Enable paced presentation stream for spectators (can combine with --presentation-delay-ms)",
    )
    parser.add_argument(
        "--presentation-delay-ms",
        type=int,
        default=1200,
        help="Delay between presentation events (milliseconds)",
    )
    args = parser.parse_args()

    move_time = 0 if args.manual_control else args.move_time

    config = TableConfig(
        seats=args.seats,
        starting_stack=args.starting_stack,
        sb=args.sb,
        bb=args.bb,
        move_time_ms=move_time,
    )

    server = HostServer(
        config,
        presentation_mode=args.presentation,
        presentation_delay_ms=args.presentation_delay_ms,
    )
    asyncio.run(server.start(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
