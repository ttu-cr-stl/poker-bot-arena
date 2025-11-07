# Poker Bot Arena – Spectator UI

Minimal React + Vite single-page viewer for the tournament WebSocket spectator feed.

## Features

- Omniscient table view (all hole cards, community, stacks, pot)
- Lightweight black-on-neon aesthetic suitable for projectors
- Inline event ticker that replays betting/action log
- Playback controls (pause, step, scrub-to-live) to slow fast hands or recap a key spot
- Demo mode (`?demo=true`) for developing without a running tournament server
- Operator mode (`?control=true`) surfaces a “Start next hand” button that issues control commands to the host when it runs in `--hand-control operator` mode

## Local development

```bash
cd spectator-ui
npm install
npm run dev
```

The dev server auto-opens on <http://localhost:5173>. Configuration follows one rule: query string overrides build-time env, which overrides defaults. Useful combos:

- `?demo=false` – force live mode even during `npm run dev` (dev defaults to demo).
- `?demo=true` – force demo frames even in production.
- `?ws=ws://127.0.0.1:8765/spectate` – point to any host; otherwise we use `VITE_SPECTATOR_WS`, then fall back to `ws(s)://<page-host>:8765/spectate`.
- `?control=true` – request operator rights (requires the server to be in `--hand-control operator`).

Production build:

```bash
npm run build
npm run preview
```

The bundle emits to `dist/` and can be hosted by any static server.

## Operator mode

When the tournament host is launched with `python -m tournament --hand-control operator`, the next hand will only start after an explicit control command. Run the spectator UI with `?control=true` (for example `http://localhost:5173/?control=true`) to unlock the control button. That WebSocket connection identifies itself as an operator, so the “Start next hand” action sends `{"type":"control","command":"START_HAND"}` to the host. Leave the query parameter off for read-only spectator views.

## WebSocket contract (draft)

The UI listens for JSON messages with a `type` starting with `spectator/`. Each message must include the omniscient table snapshot so the browser never has to reconstruct state from scratch.

| Message | Required fields | Notes |
| ------- | --------------- | ----- |
| `spectator/lobby` | `seats[{seat, team, stack, connected}]` | Broadcast on connection changes; optional but nice for pre-hand display. |
| `spectator/start_hand` | `state` (see below) | First frame for a hand. |
| `spectator/event` | `hand_id`, `event`, `state` | Append a new frame after an action, street reveal, or admin update. |
| `spectator/end_hand` | `hand_id`, `state`, `results[]` | Final frame; marks the hand as closed. |
| `spectator/snapshot` | `hand_id`, `frames[]` | Optional catch-up payload when a spectator joins mid-hand. |

`state` payload (shared across the messages above):

```json
{
  "hand_id": "H-20240324-00012",
  "table_id": "T-1",
  "pot": 320,
  "phase": "TURN",
  "community": ["Ah", "Qd", "7s", "9c"],
  "seats": [
    {"seat": 0, "team": "Bot.A", "stack": 1040, "committed": 0, "hole": ["Ad", "Ks"], "is_button": true},
    {"seat": 1, "team": "Bot.B", "stack": 940, "committed": 40, "hole": ["7c", "7d"], "has_folded": false}
  ],
  "next_actor": 1,
  "time_remaining_ms": 8300,
  "sb": 10,
  "bb": 20
}
```

`event` payload examples:

```json
{"ev": "CALL", "seat": 1, "amount": 20}
{"ev": "FLOP", "cards": ["Ah", "Qd", "7s"]}
{"ev": "POT_AWARD", "seat": 0, "amount": 320}
{"ev": "SHOWDOWN", "seat": 0, "cards": ["Ad", "Ks"], "rank": "Top pair"}
```

The UI treats every incoming frame as authoritative (no diffing based on previous history). Fields you omit will render as blanks, so ensure the snapshot stays complete.

## Deployment notes

- The build is static; hosting alongside the Python tournament server can be as simple as `python -m http.server` or serving from `nginx`.
- Set `VITE_SPECTATOR_WS` at build time to bake in the WebSocket URL (otherwise it defaults to `ws(s)://<host>:8765/spectate`).
- The playback timeline lives entirely in the browser; if you need persistent archives, log the same frames server-side (e.g., JSON Lines per hand) and expose them over HTTP for later import.
