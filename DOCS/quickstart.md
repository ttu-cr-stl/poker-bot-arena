# Student Quickstart

Follow these steps if you want to build a poker bot from scratch and test it locally.

## 1. Clone & Install
```bash
git clone <repo-url>
cd poker-bot-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## 2. Launch the Practice Server
This gives every connecting bot its own heads-up match against our baseline house bot.
```bash
python practice/server.py --host 127.0.0.1 --port 9876
```

## 3. Run the Sample Bot Template
Open a second terminal (activate the venv again) and run:
```bash
python sample_bot.py --team MyBot --code SECRET --url ws://127.0.0.1:9876/ws
```
Edit `sample_bot.py` and replace `choose_action` with your strategy. The provided template responds to every `act` prompt with a simple plan and prints host events to the terminal. Keep the JSON handshake intact.

## 4. Iterate Fast
- Add logging inside `choose_action` so you can replay decisions.
- Want to play a seat by hand? Use the manual client: `python scripts/manual_client.py --team Alice --code DEMO --url ws://127.0.0.1:9876/ws`.
- Need longer matches? Modify `practice/server.py` to tweak stacks or blinds.

## 5. Graduate to the Tournament Host
Once your bot survives practice:
```bash
python -m tournament --manual-control --presentation --presentation-delay-ms 1500
```
Use the macOS spectator app (see [`spectator/README.md`](../spectator/README.md)) to control pacing and manual skips.

## Pro Tips
- Keep your bot stateless between hands; rely on host messages for the truth.
- If you lose connection, reconnect with the same `(team, join_code)`.
- Always respond to `act` quickly—even in practice we expect a move; the tournament host has manual overrides if you freeze.

Happy hacking!
