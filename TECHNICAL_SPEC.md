# Poker Bot Arena Technical Specification (v1)

## Protocol Overview
- Variant: Single-table No-Limit Texas Hold'em
- Transport: WebSocket `ws(s)://<host>/ws`, UTF-8 JSON, one object per frame
- Seats: 2–10; default 6
- Stacks: default 10,000 chips
- Blinds: default 50/100, fixed
- Move timer: per turn, default 15,000 ms (configurable `move_time_ms`)
- Match ends when only one seat retains chips >0

## Message Envelope
```json
{
  "type": "string",
  "v": 1,
  "ts": "2025-10-13T18:22:31Z" // optional
}
```
`ts` is optional, primarily for debugging. `type` distinguishes payloads.

## Identity & Seating
- Client must send `hello` with unique `team` plus `join_code`.
- `(team, join_code)` locks a seat. Reconnecting with same credentials replaces the old connection.
- Server broadcasts `lobby` on joins/disconnects.

## Lifecycle
1. Client connects and sends `hello`.
2. Server replies `welcome` and broadcasts updated `lobby`.
3. When ≥2 stacks active, server emits `start_hand` and `event` frames (e.g., blinds).
4. Server sends private `act` to current seat; client answers with `action`.
5. Server broadcasts resulting `event` frames; progresses betting streets or awards pots.
6. At showdown or fold-out, server emits `end_hand`; if match is over, emits `match_end`, else starts next hand.

## Timing & Auto-Actions
- Timer starts when `act` is sent; duration `you.time_ms` (default `move_time_ms`).
- On expiry: prefer `CHECK` if legal; else `CALL`; else `FOLD`.
- Duplicate or late `action` messages ignored.

## Client → Server Messages
### `hello`
```json
{"type":"hello","v":1,"team":"Alpha","join_code":"KF7Q9C"}
```
Errors: `BAD_SCHEMA`, `TEAM_TAKEN`, `TEAM_UNKNOWN`.

### `action`
```json
{"type":"action","v":1,"hand_id":"H-2025-10-17-00123","action":"RAISE_TO","amount":1200}
```
- `action` ∈ {`FOLD`,`CHECK`,`CALL`,`RAISE_TO`}.
- `amount` required for `RAISE_TO`.
Errors: `INVALID_ACTION`, `OUT_OF_TURN`, `ACTION_TOO_LATE`, `BAD_SCHEMA`.

## Server → Client Messages
### `welcome`
```json
{
  "type":"welcome","v":1,
  "table_id":"T-1","seat":3,
  "config":{"variant":"HUNL","seats":8,"starting_stack":10000,"sb":50,"bb":100,"move_time_ms":15000}
}
```

### `lobby`
```json
{"type":"lobby","v":1,"players":[{"seat":0,"team":"Alpha","connected":true,"stack":10000}]}
```

### `start_hand`
```json
{
  "type":"start_hand","v":1,
  "hand_id":"H-2025-10-17-00123",
  "seed":987654321,
  "button":2,
  "stacks":[{"seat":0,"stack":10000},...]
}
```
- `stacks` include chips in pot at hand start.

### `act` (private)
```json
{
  "type":"act","v":1,
  "hand_id":"H-2025-10-17-00123",
  "seat":3,
  "phase":"FLOP",
  "you":{"hole":["Ah","Ad"],"stack":9600,"to_call":200,"time_ms":15000},
  "table":{"sb":50,"bb":100,"seats":4,"button":2},
  "players":[{"seat":0,"stack":10450,"has_folded":false,"committed":100},...],
  "community":["7h","2d","Qs"],
  "legal":["FOLD","CALL","RAISE_TO"],
  "call_amount":200,
  "min_raise_to":600,
  "max_raise_to":9600
}
```

### `event`
`ev` enumerations and additional fields:
- `POST_BLINDS` → `sb_seat`, `bb_seat`, `sb`, `bb`
- `BET` → `seat`, `amount`
- `CALL` → `seat`, `amount`
- `CHECK` → `seat`
- `FOLD` → `seat`
- `FLOP` → `cards`
- `TURN`, `RIVER` → `card`
- `SHOWDOWN` → `seat`, `hand`, `board`, `rank`
- `POT_AWARD` → `seat`, `amount`
- `ELIMINATED` → `seat`

Example:
```json
{"type":"event","v":1,"ev":"BET","seat":3,"amount":1200}
```

### `end_hand`
```json
{"type":"end_hand","v":1,"hand_id":"H-2025-10-17-00123","stacks":[{"seat":0,"stack":10450},...]}
```

### `snapshot`
```json
{
  "type":"snapshot","v":1,
  "at_hand_id":"H-2025-10-17-00123",
  "phase":"TURN",
  "you":{"seat":3,"hole":["Ah","Ad"],"stack":9400,"to_call":400},
  "players":[...],
  "community":["7h","2d","Qs","9c"],
  "next_actor":1,
  "time_ms_remaining":3200,
  "legal":["FOLD","CALL","RAISE_TO"],
  "call_amount":400,
  "min_raise_to":1200,
  "max_raise_to":9400
}
```
(legal/amount fields only included if `next_actor` equals snapshot recipient.)

### `match_end`
```json
{
  "type":"match_end","v":1,
  "winner":{"seat":6,"team":"GammaBot"},
  "final_stacks":[{"seat":6,"team":"GammaBot","stack":80000}]
}
```

### `error`
```json
{"type":"error","v":1,"code":"INVALID_ACTION","msg":"Raise below min"}
```

## Game Engine Details
- Seats tracked as `PlayerSeat` structs: `stack`, `committed`, `total_in_pot`, `hole_cards`, `has_folded`, `connected`.
- Button rotates to next active seat each hand.
- `start_hand` shuffles deck (seeded), deals 2 cards each, posts blinds (`POST_BLINDS` event), resets committed chips.
- `legal_actions(seat)` returns actions plus `call_amount` (chips needed to call) and `min_raise_to`/`max_raise_to` bounds.
- `apply_action` updates state and returns event list. For `RAISE_TO`, min raise enforced; max limited by stack.
- Phase progression: `PRE_FLOP` → `FLOP` (deal 3) → `TURN` (deal 1) → `RIVER` (deal 1) → `SHOWDOWN`.
- Side pots built by peeling contributions; each pot awarded to best eligible hand using `evaluate_best` (5-card combos).
- If only one seat remains (all others folded or busted), award entire pot, clear queues, mark `SHOWDOWN`.
- Snapshots and `act` payloads derived directly from current context.

## Timing & Reconnect Behavior
- Seat disconnects retain stack and seat ownership.
- Timer continues while disconnected if it is the player’s turn.
- Reconnecting with same credentials replaces old socket and triggers `snapshot` with remaining `time_ms`.

## Test Coverage Summary
- Button/blind setup, legal action payload integrity.
- Raise updates pot and pending callers.
- Fold-to-win results in immediate pot award, no extra prompts.
- All-in side pots and multiway splits distribute chips correctly.
- Min-raise cap when stack equals required amount.
- Zero-to-call scenarios allow `CHECK` with `call_amount` omitted.
- Post-flop fold cascade ends hand without dealing new streets.
- Match end detection when opponent busts.
- Snapshot contains legal details when reconnecting actor.
- Timeout preference order (CHECK → CALL → FOLD).
- Multi-hand rotation carries correct button/stacks.
