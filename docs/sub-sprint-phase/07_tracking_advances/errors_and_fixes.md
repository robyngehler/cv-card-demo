# Errors and Fixes – 07 Tracking Advances

This file documents relevant errors, failures, workarounds, and fixes for this phase.

---

## 2026-06-06 – State Instances Were Recreated On `run() -> None`

### Context

- state machine core
- affected states: `CANDIDATE_DETECTED`, `TRACKING`

### Observed Behavior

State objects were recreated after every `run()` call, which reset debounce counters, tracker state, and any future fusion/questionnaire state kept on the state instance.

### Expected Behavior

When `run()` returns `None`, the current state instance must stay active until an explicit transition occurs.

### Logs / Evidence

```text
Implementation review showed `StateMachine.start()` recreated the state object on every loop iteration.
```

### Suspected Cause

The state-machine loop only preserved the state name, not the active state instance.

### Fix Applied

`StateMachine` now keeps the active state instance alive until a real transition is returned, and only then calls `exit()` and creates the next state instance.

### Verification

Command:

```bash
get_errors on app/state_machine.py and affected states
```

Expected/observed result:

```text
No static analysis errors after the state-machine persistence change.
```

### Status

```text
FIXED
```

---

## 2026-06-06 – Optional Tracking Backends Missing In Windows Dev Environment

### Context

- `hand_tracker_service`
- `card_detector_service`
- current environment: Windows development machine

### Observed Behavior

Static analysis flagged unresolved optional imports for `mediapipe` and `ultralytics`.

### Expected Behavior

The tracking slice should remain statically clean and degrade gracefully when optional backends are not installed.

### Logs / Evidence

```text
Import "mediapipe" could not be resolved
Import "ultralytics" could not be resolved
```

### Suspected Cause

Direct optional imports were used in the initial service implementation.

### Fix Applied

Both services now load optional backends via `importlib` and report degraded runtime status instead of failing static validation.

### Verification

Command:

```bash
get_errors on app/services/hand_tracker_service.py and app/services/card_detector_service.py
```

Expected/observed result:

```text
No static analysis errors; services fall back to runtime status reporting when packages are absent.
```

### Status

```text
WORKAROUND
```

---

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| 2026-06-06 | Target-environment live fusion validation pending | OPEN | Requires booth camera / Jetson or equivalent runtime with optional backends installed |

---

## 2026-06-07 – Lost-Hold Hand Merge Could Stall At Anchor Score

### Context

- `app/cv/fusion_tracker.py`
- `LOST_HOLD` recovery path

### Observed Behavior

`LOST_TO_HAND_MERGE` could remain at the anchor score instead of progressing into `HAND_PROXY_ACTIVE` once the hand was stable again.

### Expected Behavior

After the lost-hold anchor is re-established against a stable hand proxy, the fusion state should proceed into live hand-driven scoring.

### Logs / Evidence

```text
Static review of the new exhaustive state table revealed that LOST_TO_HAND_MERGE lacked a forward transition.
```

### Suspected Cause

The initial lost-hold refactor added the merge state but not the follow-up branch that applies the recalculated hand offset.

### Fix Applied

`app/cv/fusion_tracker.py` now promotes `LOST_TO_HAND_MERGE` into `HAND_PROXY_ACTIVE` on the next stable hand update and reapplies the anchor-derived offset.

### Verification

Command:

```bash
get_errors on app/cv/fusion_tracker.py
```

Expected/observed result:

```text
No static analysis errors after the lost-hold merge transition fix.
```

### Status

```text
FIXED
```