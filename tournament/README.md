# Tournament Host

Use this package to run the official multi-seat tournament server.

## Key Files
- `server.py` – WebSocket host (bot seating, timers, manual skips, presentation mode).
- `__main__.py` – CLI entry point (`python -m tournament`).
- Imports everything from `core/` for poker logic.

## Quick Start
```bash
python -m tournament --host 127.0.0.1 --port 8765 --seats 6 \
    --manual-control --presentation --presentation-delay-ms 1500
```

Flags:
- `--manual-control` disables automatic timeouts; use the spectator app to force skips.
- `--presentation` enables buffered spectator output.
- `--presentation-delay-ms` controls pacing between presentation events.

See [`TECHNICAL_SPEC.md`](../TECHNICAL_SPEC.md) for JSON message formats.
