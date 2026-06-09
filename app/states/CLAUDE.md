# State Machine — `app/states/`

*Applies to all state classes under `app/states/`. Loaded automatically here.*

## Goal

Use a simple explicit state machine to keep the booth demo predictable and
recoverable.

## States

```text
BOOT
INIT_CAM
CALIBRATION
IDLE_NO_CARD
CANDIDATE_DETECTED
TRACKING
SNAPSHOT
RECOVERY
ERROR_SAFE
```

State files: `boot.py`, `init_cam.py`, `calibration.py`, `idle.py`,
`candidate_detected.py`, `tracking.py`, `snapshot.py`, `recovery.py`,
`error_safe.py`.

## State Interface

```python
class State:
    name: str

    def enter(self, ctx: AppContext) -> None:
        ...

    def run(self, ctx: AppContext) -> str | None:
        ...

    def exit(self, ctx: AppContext) -> None:
        ...
```

`run()` returns the next state name, or `None` if the state remains active.

## Required Behavior

Every state should: log entry, log exit, update health status, handle expected
failures, return explicit transitions, and avoid blocking forever.

## Transition Logging

Log every transition in this shape:

```text
STATE_TRANSITION old_state=BOOT new_state=INIT_CAM reason=boot_complete
```

## Error Handling

If a state fails: record the error, publish it to health state, transition to
`RECOVERY` or `ERROR_SAFE`, and do not silently continue with invalid assumptions.

---

## BOOT State

BOOT is the first application state. It prepares the runtime environment and then
transitions to `INIT_CAM`.

### BOOT Must Do

- load configuration
- validate configuration
- initialize logging
- create runtime context (AppContext)
- start or verify UI service
- start or verify health service
- initialize state machine runtime
- prepare optional service placeholders
- transition to `INIT_CAM`

### BOOT Must Not Do

- open the camera
- read camera frames
- run card detection
- require WLED
- block on optional external devices

### BOOT Success Criteria

```text
config OK
logging OK
AppContext OK
UI service OK
health service OK
state machine OK
```

### BOOT Failure Criteria

```text
config missing
config invalid
logging impossible
UI service cannot start
health endpoint unavailable
state machine cannot be created
```

WLED failure is **not** a BOOT failure.

---

## INIT_CAM State

INIT_CAM owns camera and OpenCV initialization. See `app/services/CLAUDE.md` for
the camera service contract.

### INIT_CAM Must Do

- verify `cv2` import / availability
- create the camera service
- open the configured camera
- read the first valid frame
- verify frame shape / validity
- optionally check requested FPS / resolution
- update UI and health status
- transition to the next state on success

### INIT_CAM Failure Handling

```text
INIT_CAM → RECOVERY        (recoverable)
INIT_CAM → ERROR_SAFE      (unrecoverable)
```

### Camera Retry Policy

Use bounded retry attempts. Do not block forever.

```text
try open camera
try read frame
if failed:
    log error
    close camera
    wait short retry interval
    retry N times
if still failed:
    transition to RECOVERY
```

### UI During INIT_CAM

The UI must already be visible before the camera is opened.

```text
on init:    "Initializing camera..."
on failure: "Camera could not be opened. Retrying..."
```

### OpenCV Scope

Keep OpenCV initialization simple. Do not introduce deep learning in INIT_CAM —
deep learning is optional and comes later.

---

## SNAPSHOT State

Triggered from `TRACKING` when capture conditions are met (card stable, no hand
interference). Orchestrates: precheck image capture, candidate validation via
`CandidatePrecheckService`, final snapshot capture via `SnapshotService`, and
post-processing (OCR, identity resolution, persistence, vector embedding). On
success transitions back to `IDLE_NO_CARD`; on failure transitions to `RECOVERY`.

## RECOVERY

Attempt controlled recovery from runtime failures such as: lost camera, frame
timeout, backend service issue, optional output failure.

## ERROR_SAFE

For critical unrecoverable failures. Show a meaningful error in the UI whenever
possible.
