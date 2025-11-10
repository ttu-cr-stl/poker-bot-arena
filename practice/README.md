# Practice Environment

Everything in this folder helps teams rehearse locally without the full tournament host.

## Files
- `server.py` – spins up the practice host. Single connections create a heads-up match (seat 0 vs the house bot in seat 1); pairing `--bot A/B` clients creates a three-seat table for A/B testing.
- `bots.py` – baseline strategy for the house bot.
- `sample_bot.py` (now at the repo root) – starter client template you can copy and customize.

## Typical Workflow
1. Start the practice server: `python practice/server.py --host 127.0.0.1 --port 9876`
2. Run the sample bot in another terminal: `python sample_bot.py --team Demo --url ws://127.0.0.1:9876/ws`
3. Tweak `choose_action` inside the sample bot, or point the practice server at your own bot script.

## A/B Testing Two Bots
Need to pit two different strategies against each other? Launch up to two clients for the same team using the new `--bot` flag (slots `A` and `B`).

1. Start the practice server as usual.
2. Launch the first bot: `python sample_bot.py --team Demo --bot A --url ws://127.0.0.1:9876/ws`
3. Launch the second bot with the same team: `python sample_bot.py --team Demo --bot B --url ws://127.0.0.1:9876/ws`

Once both clients connect, the server creates a 3-seat table: Demo (A), Demo (B), and the baseline practice bot. While waiting for the partner bot, the connected client emits a `[practice] waiting for partner` log line. You can reconnect either slot at any time; the table is reserved for that team until the match ends.

> **Team names matter.**  
> The host treats names case-insensitively (`RoboNerds` and `robonerds` collide), so agree on a single spelling with your teammates. Reusing the same name lets you reconnect instantly after a hiccup.

Bots and practice server use the same JSON protocol as the real tournament host, so no changes are required when you switch on match day.
