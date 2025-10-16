import argparse
import asyncio
import logging

from .models import TableConfig
from .server import HostServer

logging.basicConfig(level=logging.INFO)


def main() -> None:
    parser = argparse.ArgumentParser(description="Poker Bot Arena host server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seats", type=int, default=6)
    parser.add_argument("--starting-stack", type=int, default=10_000)
    parser.add_argument("--sb", type=int, default=50)
    parser.add_argument("--bb", type=int, default=100)
    parser.add_argument("--move-time", type=int, default=15_000, help="Move time in milliseconds")
    args = parser.parse_args()

    config = TableConfig(
        seats=args.seats,
        starting_stack=args.starting_stack,
        sb=args.sb,
        bb=args.bb,
        move_time_ms=args.move_time,
    )

    server = HostServer(config)
    asyncio.run(server.start(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
