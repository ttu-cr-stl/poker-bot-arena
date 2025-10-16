# Poker Bot Arena

A single-table No-Limit Texas Hold'em arena for head-to-head or multiway bot competitions. The server runs locally, exposes a WebSocket wire protocol, and ships with a manual CLI client for human playtests.

## Features
- Authoritative host server with configurable seats, blinds, and decision timer
- JSON protocol documented in [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md)
- Deterministic RNG seeded per hand for replayability
- Side-pot aware engine with snapshot/resume support
- Manual CLI client (`scripts/manual_client.py`) for human-in-the-loop testing
- Comprehensive unit tests covering betting edge cases and match lifecycle

## Quick Start
1. **Set up environment**
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e '.[dev]'
   ```

2. **Run the host**
   ```bash
   python -m host --host 127.0.0.1 --port 8765 \
       --seats 4 --starting-stack 10000 --sb 50 --bb 100 --move-time 15000
   ```
   Adjust parameters to taste (e.g., `--move-time 120000` for 2 minutes per decision).

3. **Join from the manual client** (one terminal per seat):
   ```bash
   python scripts/manual_client.py --team Alice --code A1B2C3
   python scripts/manual_client.py --team Bob   --code B1C2D3
   ```
   Use unique `(team, join_code)` pairs for each participant. Commands: press Enter for the suggested default, `h` for help, or enter `RAISE_TO` amounts when prompted.

## Development
- Run tests:
  ```bash
  python -m pytest
  ```
- View the technical wire protocol and engine behavior: [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md)
- Manual playtest walkthrough: [`MANUAL_TESTING.md`](./MANUAL_TESTING.md)

## Project Layout
```
host/                # Engine, card primitives, WebSocket host
scripts/manual_client.py  # Interactive CLI client
tests/               # Engine regression suite
TECHNICAL_SPEC.md    # Protocol and engine detail
MANUAL_TESTING.md    # Human playtest guide
```

## Roadmap Ideas
- Web UI for spectators/scoreboard
- NDJSON replay logging + replay viewer
- Sample bot SDKs (Python/TypeScript)

## License
Specify your chosen license here.
