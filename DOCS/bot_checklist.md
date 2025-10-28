# Bot Submission Checklist

Before match day, make sure your bot handles the following:

## Protocol Basics
- [ ] Send `hello` immediately after connecting (`team`, `join_code`).
- [ ] Listen for `act` messages and always respond with `action` within the allowed time.
- [ ] Handle `event`, `end_hand`, `match_end`, and `error` messages gracefully (log them, update state as needed).
- [ ] If disconnected, reconnect using the same credentials and resume play when you receive a `snapshot`.

## Decision Loop
- [ ] `choose_action` covers every legal move (fold/check/call/raise).
- [ ] You always pull `call_amount`, `min_raise_to`, and `max_raise_to` directly from the `act` payload—never guess.
- [ ] You clamp raises so they stay within the min/max range and only send integers.
- [ ] You can recover from unexpected data by defaulting to a safe action (usually fold).

## Logging & Debugging
- [ ] Print helpful logs for each decision (hand id, cards, action chosen) so you can replay issues.
- [ ] Store logs locally; the host logs minimal info to keep matches fair.

## Testing
- [ ] Run against the practice server (`practice/server.py`) and verify multiple hands play out.
- [ ] Try the manual client to simulate weird inputs.
- [ ] Run the stress script (`scripts/bot_stress.py`) with your bot swapped in to ensure it survives long sessions.

## Nice-to-haves
- [ ] Support a `--url` flag so you can point your bot at different hosts easily.
- [ ] Expose a dry-run mode where decisions are logged but not sent (handy for debugging).
- [ ] Handle command-line config for tuning (aggressiveness, thresholds).

On match day, bring your bot script, logs, and the ability to reconnect quickly. Good luck!
