# Bot Submission Checklist

Use this page as your quick “Did we cover everything?” before you hand in your bot.

---

## 1. Basic protocol
- [ ] First message after connecting is `hello` with your `team` name (case-insensitive).
- [ ] You can read `act` prompts and reply with `action` within the time limit.
- [ ] You handle `event`, `end_hand`, `match_end`, and `error` messages without crashing.
- [ ] If you disconnect, restarting with the same team name reclaims your seat.

## 2. Making decisions
- [ ] Your bot can send any legal move (`FOLD`, `CHECK`, `CALL`, `RAISE_TO`).
- [ ] You use the numbers provided in each `act` payload (`call_amount`, `min_raise_to`, `max_raise_to`, `pot`, `current_bet`, `min_raise_increment`, and your own `committed` chips).
- [ ] Raises are clamped so they stay inside the allowed range and are integers.
- [ ] If something unexpected happens, you fall back to a safe action (usually fold).

## 3. Logging
- [ ] You log the hand id, cards, and chosen action so you can replay decisions.
- [ ] Logs are saved on your device (the host keeps minimal logs).

## 4. Testing
- [ ] You’ve played several hands on the practice server (`practice/server.py`) with no errors.
- [ ] You tried the manual client to understand the prompts.
- [ ] You let your bot play a long session (hundreds of hands) without crashing or leaking resources.
- [ ] You ran the automated tests:
  ```bash
  python -m pytest
  ```

## 5. Nice extras (optional but helpful)
- [ ] Your bot accepts a `--url` flag so you can switch between practice and tournament hosts.
- [ ] There’s a “dry run” mode that prints actions instead of sending them (good for debugging).
- [ ] You support command-line flags for tuning strategy parameters.

---

Bring your bot script, your team name, and the ability to reconnect quickly. If every box is checked, you’re ready. Good luck out there!
