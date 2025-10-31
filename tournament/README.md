# Tournament Host

Use this package to run the official multi-seat tournament server.

## Key Files
- `server.py` – WebSocket host (bot seating, timers, manual skips).
- `__main__.py` – CLI entry point (`python -m tournament`).
- Imports everything from `core/` for poker logic.

## Quick Start
```bash
python -m tournament --host 127.0.0.1 --port 8765 --seats 6 --manual-control
```

Flags:
- `--manual-control` disables automatic timeouts so you can force skips from the CLI (useful during live events).

See [`TECHNICAL_SPEC.md`](../TECHNICAL_SPEC.md) for JSON message formats.
