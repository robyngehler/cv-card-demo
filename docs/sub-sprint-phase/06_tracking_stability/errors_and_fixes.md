# Errors and Fixes – 06 Tracking Stability

## Status

```text
TRACKING_CONTINUITY_IMPLEMENTED
```

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| 2026-06-05 | Live camera hand-occlusion run still pending after tracker rewrite | OPEN | Functional regression script already passes |

## 2026-06-05 – Tracking Dropped Too Early

### Context

- state: `TRACKING`
- state-machine contract: `run() -> None` means stay active
- user-visible symptom: score disappeared when a hand covered or moved the card

### Observed Behavior

Tracking used `candidate_max_lost_frames` together with `idle_poll_interval`, reused the last pose without prediction, and the state machine could stop entirely when a state returned `None`.

### Expected Behavior

Short occlusions should keep the UI alive, tracking should resume on the same card when it reappears nearby, and the state machine should continue running until an explicit transition occurs.

### Suspected Cause

The previous implementation mixed detection confirmation thresholds with active tracking behavior and had no dedicated continuity model.

### Fix Applied

- Added `CardTracker` with velocity smoothing, prediction, and timeout-based expiry.
- Matched visible candidates against the predicted position instead of always taking the highest-confidence contour.
- Published `score`, `state`, and `source` so the UI can distinguish normal tracking from short occlusion hold.
- Fixed `StateMachine.start()` to remain in the current state when `run()` returns `None`.

### Verification

Command:

```bash
python scripts/test_tracking_continuity.py
python -m py_compile app/cv/card_tracker.py app/cv/classical_card_detector.py app/states/idle.py app/states/candidate_detected.py app/states/tracking.py app/state_machine.py
```

Expected/observed result:

```text
PASS
tracking continuity checks passed
```

### Status

```text
FIXED
```