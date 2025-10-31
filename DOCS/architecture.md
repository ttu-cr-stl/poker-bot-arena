# Architecture Overview

Poker Bot Arena is built around three layers:

1. **Game Engine (`core/game.py`)**
   - Pure No-Limit Hold'em rules: dealing, betting rounds, side pots, hand evaluation.
   - No networking here—just Python objects.

2. **Tournament Host (`tournament/server.py`)**
   - Manages seats, WebSocket clients (bots), timers, and manual skips.
   - Each table shares a single `GameEngine` instance; bots listen for `act` prompts and respond with `action` messages.

3. **Clients**
   - **Bots**: Student-written WebSocket clients that handle `hello`, `act`, and basic event messages.
   - **Practice Server (`practice/server.py`)**: spins up a fresh `GameEngine` per connection so students can scrimmage locally against the baseline house bot.

```
Remote Bot ─┐
            ├─ WebSocket ── Tournament Host
Practice    │
Server ─────┘
Baseline Bot
```

## Message Flow
All WebSocket messages are JSON objects with a `type` field (`hello`, `act`, `action`, `event`, etc.). The full schema lives in [`TECHNICAL_SPEC.md`](../TECHNICAL_SPEC.md).

Key events:
- `start_hand`: new hand begins (button position, stacks).
- `act`: current seat must respond with `action`.
- `event`: public updates like `BET`, `CALL`, `FLOP`, etc.
- `end_hand`: pot settled; stacks updated.
- `admin`: manual operator actions (e.g., forced skip).

Practice and tournament hosts share the same protocol so bots can move between them without changes.

## File Guide
- `core/`: poker rules, cards, evaluators, data models.
- `tournament/`: multi-seat WebSocket host.
- `practice/`: easy scrimmage environment and sample bot.
- `scripts/`: utilities (manual client, stress runner).
- `tests/`: pytest suite covering engine and server edge cases.

Start in `practice/` to build confidence, then plug into the tournament host for full matches.
