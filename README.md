# Poker Bot Arena

Welcome! This repo powers our campus Poker Bot Arena. The aim is to make it dead simple for new teams to build a WebSocket bot, scrimmage locally, and then battle on the tournament host.

## Choose Your Path
- **Student practice** → Start with the Quickstart below.
- **Organizers/spectator display** → See the Organizer Notes.
- **Engine deep dive** → Head to [`DOCS/architecture.md`](./DOCS/architecture.md).

## Quickstart (two terminals)
1. **Set up Python**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e '.[dev]'
   ```
2. **Terminal #1 – practice server**
   ```bash
   python practice/server.py --host 127.0.0.1 --port 9876
   ```
   This spins up a fresh heads-up table for each connecting bot vs our baseline “house” bot.
3. **Terminal #2 – sample bot template**
   ```bash
   python sample_bot.py --team Demo --code DEMO --url ws://127.0.0.1:9876/ws
   ```
   Edit `choose_action` inside `sample_bot.py` to plug in your own strategy.
4. **Want human vs. bot?**
   ```bash
   python scripts/manual_client.py --team Alice --code A1B2C3 --url ws://127.0.0.1:9876/ws
   ```
   Use `h` at the prompt for command hints.

More tips live in [`practice/README.md`](./practice/README.md).

## Organizer Notes
- Tournament host (multi-seat tables, spectators, manual skips, presentation mode) lives under `tournament/`.
- macOS spectator app source is under `spectator/`. Launch the host with `--presentation` for paced visuals and `--manual-control` when you need full operator control.
- Need humans to play on the tournament host? `scripts/manual_client.py` works there too.
- Run tests anytime with `python -m pytest`.

## Project Layout
```
DOCS/              # newcomer-friendly guides and architecture diagrams
core/              # poker rules, cards, evaluators, data models
tournament/        # network host that drives the official table
practice/          # per-connection scrimmage server + sample bot
scripts/           # manual client, stress tools
spectator/         # SwiftUI spectator display
tests/             # regression suite
TECHNICAL_SPEC.md  # protocol reference
```

## Learn More
- [`DOCS/quickstart.md`](./DOCS/quickstart.md) – a longer student onboarding guide.
- [`DOCS/bot_checklist.md`](./DOCS/bot_checklist.md) – must-haves before the tournament.
- [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) – full JSON wire protocol for both tournament and practice hosts.

Good luck building your bot!
