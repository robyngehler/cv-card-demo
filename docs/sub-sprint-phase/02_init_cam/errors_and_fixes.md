# Errors and Fixes – 02 Init Camera

This file documents relevant camera initialization errors, failures, workarounds, and fixes for the `INIT_CAM` phase.

---

## Status

```text
IN_PROGRESS
```

---
## 2026-06-05 – IDLE_NO_CARD exited immediately after enter

### Context

- state: `IDLE_NO_CARD`
- service: `StateMachine`
- command: `python -m app.main --config config/config.yaml --initial-state BOOT`

### Observed Behavior

The application transitioned to `IDLE_NO_CARD` and then immediately logged `Exiting IDLE_NO_CARD state`.

### Expected Behavior

The `IDLE_NO_CARD` state should remain active while waiting for a card, keeping the backend running and the UI available.

### Suspected Cause

`IdleNoCardState.run()` returned `None` immediately, so the state machine treated the state as complete and exited.

### Fix Applied

- Added a persistent idle loop in `app/states/idle.py`
- Added `idle_poll_interval` camera config setting
- Added runtime camera health check during idle

### Verification

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected/observed result:

- `IDLE_NO_CARD` remains active
- UI stays available
- camera is still tracked while idle

### Status

```text
FIXED
```

---
## 2026-06-05 – Camera device not available during INIT_CAM

### Context

- state: `INIT_CAM`
- service: `camera_service`
- command: `python -m app.main --config config/config.yaml --initial-state BOOT`

### Observed Behavior

The application attempted to open `/dev/video0` and failed three times.

### Expected Behavior

The camera should open and the first valid frame should be read.

### Logs / Evidence

```text
Opening camera device 0
Camera initialization attempt 1/3 failed: Camera device 0 could not be opened
Opening camera device 0
Camera initialization attempt 2/3 failed: Camera device 0 could not be opened
Opening camera device 0
Camera initialization attempt 3/3 failed: Camera device 0 could not be opened
```

### Suspected Cause

The current host environment does not expose a usable camera at device index `0`.

### Fix Applied

- Added `InitCamState` with a bounded retry loop
- Captures and logs camera initialization failures
- Transitions to `RECOVERY` after repeated failures

### Verification

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected/observed result:

```text
BOOT completes
INIT_CAM logs camera open attempts
Failure is logged and transition to RECOVERY occurs
```

### Status

```text
OPEN
```

---

## 2026-06-05 – Uvicorn startup argument caused BOOT failure

### Context

- state: `BOOT`
- service: `ui_service`
- command: `python -m app.main --config config/config.yaml --initial-state BOOT`

### Observed Behavior

Startup failed with:

```text
Config.__init__() got an unexpected keyword argument 'install_signal_handlers'
```

### Expected Behavior

The UI service should start successfully during BOOT.

### Logs / Evidence

```text
UI service failed to start: Config.__init__() got an unexpected keyword argument 'install_signal_handlers'
```

### Suspected Cause

The installed `uvicorn` version does not support `install_signal_handlers` in `Config`.

### Fix Applied

Removed `install_signal_handlers=False` from `uvicorn.Config(...)` in `app/services/ui_service.py`.

### Verification

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected/observed result:

```text
UI service started on http://0.0.0.0:8000
BOOT transitions to INIT_CAM
```

### Status

```text
FIXED
```
