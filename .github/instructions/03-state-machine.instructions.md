---
applyTo: "app/states/**/*.py"
---

# State Machine Instructions

## Goal

Use a simple explicit state machine to keep the booth demo predictable and recoverable.

## States

Known states:

```text
BOOT
INIT_CAM
CALIBRATION
IDLE_NO_CARD
CANDIDATE_DETECTED
TRACKING
STABLE_RATING
LOST_HOLD
RECOVERY
ERROR_SAFE
```

## State Interface

Each state should roughly follow:

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

`run()` returns the next state name or `None` if the state remains active.

## Required Behavior

Every state should:

- log entry
- log exit
- update health status
- handle expected failures
- return explicit transitions
- avoid blocking forever

## Transition Logging

Every transition should be logged in this shape:

```text
STATE_TRANSITION old_state=BOOT new_state=INIT_CAM reason=boot_complete
```

## Error Handling

If a state fails:

- record the error
- publish it to health state
- transition to `RECOVERY` or `ERROR_SAFE`
- do not silently continue with invalid assumptions

## BOOT

BOOT should prepare the runtime environment and then transition to INIT_CAM.

BOOT must not open the camera.

## INIT_CAM

INIT_CAM owns camera and OpenCV initialization.

## RECOVERY

RECOVERY should attempt controlled recovery from runtime failures such as:

- lost camera
- frame timeout
- backend service issue
- optional output failure

## ERROR_SAFE

ERROR_SAFE is for critical unrecoverable failures.

The UI should show a meaningful error whenever possible.
