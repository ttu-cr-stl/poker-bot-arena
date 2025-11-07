# Student Quickstart

Hi! This page is the fastest way to go from a fresh clone to a bot that can play hands. No prior poker software experience required.

---

## 1. Clone the repo and install tools

Open a terminal and run:
```bash
git clone <repo-url>
cd poker-bot-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```
The last command installs the WebSocket library and the test tools we use.

---

## 2. Start the practice server

This server gives each connecting bot its own heads-up match against the built-in house bot.
```bash
python practice/server.py --host 127.0.0.1 --port 9876
```
Leave this terminal window running—you’ll play against it from another window.

---

## 3. Run the sample bot

Open a second terminal, activate the virtual environment again, and run:
```bash
source .venv/bin/activate
python sample_bot.py --team MyBot --url ws://127.0.0.1:9876/ws
```
You should see messages like `WELCOME`, `START_HAND`, and `act`. The bot already knows the protocol; you only need to change the decision logic in `choose_action`. The template now guards against illegal moves—if your code asks for an invalid action, it logs a warning and falls back to a safe check/call/fold instead of letting the host eject you.

---

## 4. Try a hand yourself

Want to click buttons and see the protocol in action? Use the manual client:
```bash
python scripts/manual_client.py --team Alice --url ws://127.0.0.1:9876/ws
```
Type `h` at the prompt to see what the legal moves mean. This uses the exact same messages your bot receives.

---

## 5. Iterate on your strategy

- Add `print()` or logging inside `choose_action` so you can review why the bot made each move.
- Keep your own notes on the hand id (`hand_id`), stack sizes, and community cards—those are all sent in the `act` payload.
- If you lose connection, simply restart with the same `--team`; the practice server and tournament host both recognize the name (case-insensitive) and let you reclaim the seat.

---

## 6. When you’re ready, reach for the tournament host

To rehearse the on-stage experience (timers plus manual override controls), start the tournament host:
```bash
python -m tournament --manual-control
```
`--manual-control` turns off automatic timeouts so an operator can force skips—handy during live events. Most teams stay on the practice server until their bot is stable, then run a few matches on the full host to double-check behaviour.

---

## Friendly reminders

- Keep your bot stateless between hands; the host tells you everything you need.
- Always reply to `act` quickly—the organizers expect it even during practice.
- Pick a team name and stick with it—connections are matched by name (case-insensitive).

Happy hacking! If something feels unclear, reach out to the organizers or open an issue—we’re here to help.☴
