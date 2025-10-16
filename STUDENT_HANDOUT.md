# Battle of the Bots – Player Guide

Welcome to Poker Bot Arena! This handout tells you exactly what to build, how to test it, and what happens on match day. The goal is simple: connect your bot over WebSockets and play No-Limit Texas Hold'em against other teams. Everything here assumes the current implementation in this repo.

## What You Need to Deliver
1. **A poker bot** that connects to `ws://<arena-host>/ws` and plays heads-up/multiway NLHE using the JSON protocol below.
2. **A join code** supplied by the organizers. This locks your seat; keep it private.
3. **Basic logging** on your side so you can debug decisions (recommended).

You do **not** need to run a UI, build a database, or host your own server. We provide the arena.

## Setup Checklist
1. Clone the repo so you have the protocol docs and manual tools.
2. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e '.[dev]'
   ```
3. Read the protocol summary below (full detail lives in [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md)).
4. Use the manual client to practice human vs. human or human vs. bot:
   ```bash
   python scripts/manual_client.py --team Alice --code A1B2C3
   ```

## How a Match Works
- Seats: 2–10 (we’ll announce the exact count). Everyone starts with the same stack.
- Small blind / big blind: default 50/100.
- Decision clock: default 15 seconds (can be extended; organizers will confirm). If you time out, the server CHECKs if legal, otherwise CALLs, otherwise FOLDs for you.
- The arena is authoritative—whatever it says is law.
- When only one stack is left, the server broadcasts `match_end` and the game stops.

## Wire Protocol (Quick Reference)
Every message includes `{"type": ..., "v": 1}`.

### You → Arena
1. **hello** (first frame)
   ```json
   {"type":"hello","v":1,"team":"YourBot","join_code":"ABC123"}
   ```
2. **action** (responding to `act`)
   ```json
   {"type":"action","v":1,"hand_id":"H-...","action":"CALL"}
   ```
   Actions: `FOLD`, `CHECK`, `CALL`, `RAISE_TO` (`amount` required for raises).

### Arena → You
- `welcome`: your seat + table config
- `lobby`: who is seated and connected
- `start_hand`: hand ID, shuffle seed, button, stacks
- `act` (private): contains hole cards, stacks, legal moves, min/max raise
- `event`: public updates (`BET`, `FLOP`, `POT_AWARD`, etc.)
- `end_hand`: final stacks after each hand
- `match_end`: winner + final stacks
- `snapshot`: sent when you reconnect mid-hand
- `error`: if you send something invalid

See [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) for JSON fields if you need more detail.

## Bot Skeleton (Python Example)
```python
import asyncio, json, websockets

async def play(team, code, url="ws://127.0.0.1:8765/ws"):
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"type":"hello","v":1,"team":team,"join_code":code}))
        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "act":
                legal = msg["legal"]
                action = "CALL" if "CALL" in legal else legal[0]
                payload = {"type":"action","v":1,"hand_id":msg["hand_id"],"action":action}
                if action == "RAISE_TO":
                    payload["amount"] = msg["min_raise_to"]
                await ws.send(json.dumps(payload))
            elif msg["type"] == "match_end":
                break

asyncio.run(play("DemoBot", "DEMO42"))
```
This is intentionally simple—replace the decision logic with your own strategy.

## Testing Tips
- **Local arena**: run `python -m host --host 127.0.0.1 --port 8765 --seats 4`. Connect two manual clients or bots and play out a few hands.
- **Unit tests**: `python -m pytest` exercises engine edge cases (side pots, timeouts, etc.). Skim them to understand server behavior.
- **Logging**: capture `act` and `event` messages you receive so you can replay decisions.
- **Timeout drill**: intentionally sleep longer than `move_time_ms` to see how the arena defaults your action.

## When We Publish a Public Test Endpoint
We’ll share the URL and schedule once it’s live. Expect a single table running all week, reset nightly. You’ll be able to aim your bot at the remote URI without changing protocol code. This section will be updated with connection details when ready.

## Race-Day Checklist
- Bot connects and stays connected (reconnect logic tested).
- Responds to every `act` with a valid action before the timer expires.
- Handles `snapshot` after reconnecting (if your process or network blips).
- Resets internal state at `end_hand`.
- Displays logs/metrics so you can debug quickly.

## Need Help?
- Protocol deep dive: [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md)
- Manual testing steps: [`MANUAL_TESTING.md`](./MANUAL_TESTING.md)
- Host source: `host/`
- Example client: `scripts/manual_client.py`

If you run into issues, talk to the organizers during office hours or reach out via the event’s official communication channel.
