# Practice Environment

Everything in this folder helps teams rehearse locally without the full tournament host.

## Files
- `server.py` – spins up a new heads-up table for every WebSocket connection. Your bot sits in seat 0; the house baseline bot sits in seat 1.
- `bots.py` – baseline strategy for the house bot.
- `sample_bot.py` (now at the repo root) – starter client template you can copy and customize.

## Typical Workflow
1. Start the practice server: `python practice/server.py --host 127.0.0.1 --port 9876`
2. Run the sample bot in another terminal: `python sample_bot.py --team Demo --code DEMO --url ws://127.0.0.1:9876/ws`
3. Modify `choose_action` inside the sample bot, or point the practice server at your own bot script.

Bots and practice server use the same JSON protocol as the real tournament host, so no changes are required when you switch on match day.
