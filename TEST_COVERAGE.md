# Test Coverage Overview

This repository now includes focused pytest suites that align with the stress‑testing checklist.

## 1. Error Handling & Edge Cases
- `tests/test_error_handling.py` guards against illegal checks, malformed calls, inactive seats, unsupported actions, and deck exhaustion.
- `tests/test_state_management.py` verifies chip accounting and button rotation when players bust or reconnect.

## 2. Hand Evaluation System
- `tests/test_evaluator.py` walks every ranking bucket (high card through straight flush), validates kicker comparisons, wheel straights, and rejects invalid card labels.

## 3. Complex Betting Scenarios
- `tests/test_complex_betting.py` forces sequential raises to ensure min-raise increments and last-raiser updates, and scripts multiway all-ins to inspect side-pot construction and distribution.

## 4. State Management
- `tests/test_state_management.py` restarts interrupted hands, checks lobby connectivity flags, and confirms stack/pot bookkeeping never underflows.

## 5. Performance & Stress Testing
- `tests/test_stress.py` runs ≥1,000 auto-played hands with six seats, asserting chip conservation, and enforces table capacity limits.

## 6. Integration Testing
- `tests/test_integration.py` drives the async host server with dummy websockets, checking turn validation, timer-driven fallback actions (check → call → fold), and match-end signaling.

## Running The Suite
```bash
. .venv/bin/activate
python -m pytest
```

## Stress Harness With Live Bots
- `scripts/bot_stress.py` spins up the host server plus a configurable set of sample bots over real WebSocket connections.
- Each bot’s decision logic lives in the `STRATEGIES` list; swap out the callables there to prototype new behaviours quickly.
- Example run (plays 200 hands with four bots):
  ```bash
  python scripts/bot_stress.py --hands 200 --log-level INFO
  ```
