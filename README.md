# Poker Bot Arena

Welcome! This project walks you from “I just opened the repo” to “my bot is ready for the campus poker tournament.” The README explains:
- what each folder does,
- how to set up your computer,
- how to practice against our baseline bot,
- what the host expects during the real event.

---

## 1. Repo tour (what’s in each folder)

```
core/         Card shuffling, hand evaluation, betting rules (no networking)
practice/     Mini server for solo heads-up practice or two-bot A/B tests vs our “house” bot
tournament/   Real tournament server (many seats, timers)
scripts/      Extra tools: manual client, stress scripts
tests/        Automated tests that keep the poker logic safe
DOCS/         Supplemental guides (architecture, quickstart, checklist)
sample_bot.py Example bot you can copy and edit
```

Key ideas:
- **Practice server ⇔ your bot.** Every time you connect, you get a private heads-up game versus the house bot. Perfect for testing.
- **Tournament host ⇔ the real event.** Same protocol as practice, but with many seats and move timers.
- **Clients speak JSON.** You send and receive simple JSON messages over WebSockets—no special libraries needed.

---

## 2. First-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Tips:
- Python 3.9 or newer works (3.11+ is great).
- Each new terminal needs `source .venv/bin/activate`.
- Re-run `pip install -e '.[dev]'` if the requirements change.

---

## 3. Get the big picture

While the install finishes, skim these short guides:
- [`DOCS/architecture.md`](DOCS/architecture.md): how the engine, practice host, and tournament host fit together.
- [`DOCS/quickstart.md`](DOCS/quickstart.md): step-by-step practice walkthrough with screenshots.
- [`DOCS/bot_checklist.md`](DOCS/bot_checklist.md): everything the organizers will check before match day.

---

## 4. Your first scrimmage (two terminals)

**Terminal A** – start the practice server:
```bash
python practice/server.py --host 127.0.0.1 --port 9876
```

**Terminal B** – run the sample bot:
```bash
python sample_bot.py --team Demo --url ws://127.0.0.1:9876/ws
```

You’ll see `WELCOME`, `START_HAND`, and then `act` prompts. Edit the `choose_action` function and rerun to test new ideas. Seat 0 is always you; seat 1 is the house bot. The template now sanity-checks whatever you return—if you accidentally send an illegal action (bad raise size, typo, etc.) it logs a warning and falls back to the safest legal move instead of getting kicked.

Prefer playing manually? Use:
```bash
python scripts/manual_client.py --team Alice --url ws://127.0.0.1:9876/ws
```

Press `h` at the prompt for help on available actions.

### Optional: pit two strategies against each other

Run two bots with the same team name but different slots to launch a three-seat table (Bot A, Bot B, plus the house bot). Example:

```bash
python sample_bot.py --team Demo --bot A --url ws://127.0.0.1:9876/ws
python sample_bot.py --team Demo --bot B --url ws://127.0.0.1:9876/ws
```

Each client logs `[practice] waiting for partner` until both slots connect. Once a match starts, the table stays reserved for that team until the session ends, so you can restart either bot mid-match without losing the seat.

---

## 5. Building a bot (your options)

1. **Copy the template** – duplicate `sample_bot.py`, rename it, and replace the logic inside `choose_action`. The helper will clamp/correct invalid actions for you, but you’ll still see warnings if your strategy misbehaves.
2. **Write your own client** – follow the same message flow as the template. The essentials:
   - First message = `{"type": "hello", "v": 1, "team": "..."}`. Team names are case-insensitive; `RoboNerds` and `robonerds` refer to the same seat.
   - Whenever you receive `type="act"`, reply quickly with `{"type": "action", "hand_id": "...", "action": "...", "amount": maybe}`. The default timer is 15 seconds.
   - Expect other messages (`event`, `start_hand`, `end_hand`, `match_end`, `error`) at any time.
   - If your bot disconnects, reconnect with the same team name to reclaim the seat. The host now pauses on that seat until you return (or an operator skips/forfeits you), so you won’t get auto-checked out of the pot while rebooting.

Helpful facts:
- In heads-up play the dealer posts the small blind and acts first pre-flop; after the flop, the other player acts first.
- Each `act` payload already gives you the pot size, current bet, minimum raise increment, call amount, and how many chips you’ve already committed. No need to recalc them.
- Legal actions are plain strings: `FOLD`, `CHECK`, `CALL`, `RAISE_TO`. Raises are “raise to a total amount,” not “raise by this increment.”

---

## 6. Is your bot tournament-ready?

Work through this short checklist:

1. **Talk the protocol**
   - Play several hands on the practice server without errors.
   - Kill your bot mid-hand, restart it, and check that it reconnects to the same seat.
2. **Respect the timer**
   - Answer each `act` prompt within the time limit. If you don’t, the host auto-acts for you (prefers check, then call, then fold).
3. **Use the provided numbers**
   - Pull `call_amount`, `min_raise_to`, `max_raise_to`, `pot`, `current_bet`, and `min_raise_increment` straight from the payload. If you send an illegal raise, the host rejects it.
4. **Reset after each hand**
   - Handle `end_hand` and `match_end` cleanly; clear any hand-specific state.
5. **Stress test**
   - Let your bot battle the house bot for hundreds of hands (or use your own opponent). This shakes out rare bugs.
6. **Run the automated tests**
   ```bash
   python -m pytest
   ```
   Our tests cover the engine. They should pass before you submit updates.

> **Pick a name and stick with it.** Connections are claimed by team name (case-insensitive), so using the same spelling every time avoids collisions.

---

## 7. Tournament day: what to expect

1. The organizers give you a WebSocket URL (for example `ws://tournament-host:8765/ws`).
2. On your laptop:
   ```bash
   source .venv/bin/activate
   python my_bot.py --team <TeamName> --url ws://tournament-host:8765/ws
   ```
3. Your logs should show `WELCOME` and the lobby information. If you get `TABLE_FULL`, alert staff.
4. If you disconnect, reconnect with the same team name to reclaim your seat.
5. Your logs only reflect `act` prompts and timer updates; nothing else can interfere with your seat.

Organizers can pause the clock if needed, but you should plan on the normal timers being active.

**Running the showcase table.** On tournament day we typically launch the host with manual pacing:

```bash
python -m tournament --host 0.0.0.0 --port 8765 --seats <team_count> --hand-control operator
```

That keeps the table paused between hands until the operator clicks “Start next hand” in the spectator UI (`?control=true`). Use automatic mode (the default) during local practice when you don’t need the extra ceremony.

---

## 8. Spectator & operator dashboard primer

Running a stream or acting as the table operator? The `spectator-ui/` app has your back:

- **Hand timeline:** Each entry shows the winner’s best five-card combo plus the final pot share, so browsing history from the sidebar stays readable even inside the narrow layout.
- **Replay controls:** Playhead/target playback means the speed slider applies immediately (including at the start of a new hand). The updated presets keep 1× at a broadcast-friendly cadence, and you can still scrub freely.
- **Autoplay batches:** When you queue multiple auto-hands, playback jumps straight to the newest frame instead of replaying each card in slow motion.
- **Event ticker:** The ticker keeps a fixed two-line height and cycles through the most recent actions and street transitions, which keeps the table shell from jumping.
- **Seat panels:** Skip/forfeit controls are unobtrusive dots, the action label resets each street, and a red badge denotes disconnected bots while their stacks/cards remain visible.
- **Disconnect handling:** The host now waits for a disconnected team to return (or for an operator skip/forfeit) rather than auto-checking them. Once they reconnect, the pending `act` payload is resent and play resumes.

---

## 9. Helpful links

- [`DOCS/architecture.md`](DOCS/architecture.md) – big-picture overview.
- [`DOCS/quickstart.md`](DOCS/quickstart.md) – the freshman-friendly setup guide.
- [`DOCS/bot_checklist.md`](DOCS/bot_checklist.md) – quick self-test before the event.
- [`practice/README.md`](practice/README.md) – practice server tips.
- `tests/` – peek at `test_game_engine.py` and `test_integration.py` to see how we cover edge cases.

---

## 10. Need to tweak or contribute?

If you spot a bug or want to improve the project:
1. Open an issue that explains what you saw and what you expected.
2. Include steps to reproduce it.
3. Send a pull request with the fix and a matching test.

We run `python -m pytest` (and usually a short practice match) before merging changes.

---

## 11. Final words

Focus on three things: understand the JSON messages, keep your bot responsive, and test against the practice host until it feels routine. Do that and tournament day will be smooth. Good luck—and may the turn and river treat you well! 🎴
