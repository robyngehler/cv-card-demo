# CV-Card-Demo – INIT_CAM Step Specification

**Project:** CV-Card-Demo  
**Phase:** `02_init_cam`  
**Application State:** `INIT_CAM`  
**Document Status:** Detailed implementation draft  
**Target Platform:** NVIDIA Jetson Orin NX, Ubuntu 22.04.5 LTS, JetPack 6.1, Jetson Linux R36.4.x  
**Primary Goal:** Open the configured camera, verify OpenCV frame acquisition, and transition to `IDLE_NO_CARD` on success.  
**WLED:** Not relevant for this phase. Must remain optional and non-blocking.

---

## 1. Purpose of `INIT_CAM`

The `INIT_CAM` state is responsible for initializing the camera subsystem after the application has successfully completed the `BOOT` state.

`BOOT` prepares the runtime environment, starts the backend/UI, and creates the state machine.  
`INIT_CAM` is the first state that interacts with OpenCV and camera hardware.

The goal is simple:

```text
BOOT complete
  ↓
INIT_CAM enters
  ↓
OpenCV is available
  ↓
camera service is created
  ↓
camera device is opened
  ↓
first valid frame is read
  ↓
camera status is published
  ↓
transition to IDLE_NO_CARD
```

If camera initialization repeatedly fails:

```text
INIT_CAM
  ↓
RECOVERY
```

or, for unrecoverable configuration/runtime errors:

```text
INIT_CAM
  ↓
ERROR_SAFE
```

---

## 2. Scope

This phase includes:

- creating or completing `InitCamState`
- probing OpenCV availability
- opening a configured camera device
- reading the first valid frame
- validating frame shape and capture success
- updating health status during initialization
- publishing UI status updates
- retrying camera initialization with bounded attempts
- transitioning to `IDLE_NO_CARD` on success
- transitioning to `RECOVERY` after repeated camera failures
- keeping WLED optional and completely outside the critical path

---

## 3. Non-Goals

This phase explicitly does not include:

- detecting business cards
- segmenting or tracking objects
- calculating card pose
- mapping score values
- updating ranking bars based on card position
- sending LED output to WLED
- using YOLO, SAM, TensorRT, or any deep learning model
- implementing full calibration
- implementing final production-grade camera abstraction

The phase should stay focused.  
No architecture sightseeing tour, please.

---

## 4. Relation to Current Project Status

The global project checklist currently marks:

```text
01 Boot        DONE
02 Init Camera IN_PROGRESS
03 UI Service  IN_PROGRESS
09 Deployment  IN_PROGRESS
10 WLED Output OPTIONAL
```

The MVP still requires successful camera opening and OpenCV frame acquisition before card detection can proceed.

The current `02_init_cam` checklist already records:

- `InitCamState` exists
- `CameraService` exists with `cv2` probe and frame read
- retry loop for camera open/read exists
- manual test steps are documented
- recovery/error handling and health updates still require stabilization

Existing documented issues include:

- unavailable `/dev/video0` during local testing
- `IDLE_NO_CARD` previously exiting immediately
- an already fixed `uvicorn` argument compatibility issue

This document should be treated as the detailed behavioral specification for finishing and stabilizing `INIT_CAM`.

---

## 5. System Context

The expected state flow is:

```text
BOOT
  ↓
INIT_CAM
  ↓
IDLE_NO_CARD
```

Failure path:

```text
BOOT
  ↓
INIT_CAM
  ↓
RECOVERY
  ↓
INIT_CAM
```

Critical failure path:

```text
BOOT
  ↓
INIT_CAM
  ↓
ERROR_SAFE
```

`INIT_CAM` assumes that:

- config was loaded in `BOOT`
- logging is active
- UI service is available
- health endpoint is available
- state machine is running
- WLED is disabled or optional
- camera is not yet opened

---

## 6. Responsibilities of `INIT_CAM`

### 6.1 OpenCV Availability

`INIT_CAM` must verify that OpenCV can be imported and used.

Minimum check:

```python
import cv2
cv2.__version__
```

This check should happen inside `INIT_CAM`, not only in `preflight.sh`.

Why?

- `preflight.sh` is useful but optional.
- `INIT_CAM` must remain self-contained.
- Runtime errors should be visible through the UI and health status.

Expected status values:

```text
cv2.status = OK
cv2.version = <detected version>
```

Failure:

```text
cv2.status = ERROR
next_state = ERROR_SAFE
```

If OpenCV cannot be imported, recovery is usually not meaningful because the runtime environment is broken.

---

### 6.2 Camera Service Creation

`INIT_CAM` must create or access a `CameraService`.

The service is responsible for:

- opening the camera
- reading frames
- closing/releasing the camera
- reporting camera health
- exposing last valid frame metadata
- supporting retry/reconnect logic

`INIT_CAM` should not contain low-level camera code directly.

Preferred separation:

```text
InitCamState
  controls state behavior and transitions

CameraService
  controls camera hardware interaction

HealthService
  stores camera/cv2 status

UiService
  publishes status messages
```

---

### 6.3 Camera Opening

The camera should be opened using the configured backend.

MVP configuration example:

```yaml
camera:
  preferred_backend: "opencv"
  device_index: 0
  width: 1280
  height: 720
  fps: 30
  open_timeout_s: 2.0
  read_timeout_s: 2.0
  init_retry_attempts: 3
  init_retry_delay_s: 0.5
  idle_poll_interval_s: 0.1
```

Initial MVP behavior may use:

```python
cv2.VideoCapture(device_index)
```

Later, if needed, backend-specific implementations can be added:

```text
OpenCV default backend
OpenCV V4L2 backend
GStreamer pipeline
pypylon industrial camera backend
```

But for the MVP, do not build a generic camera framework unless needed.  
The demo needs frames, not a camera philosophy department.

---

### 6.4 First Frame Read

After opening the camera, `INIT_CAM` must read at least one valid frame.

Valid frame criteria:

```text
capture_success == True
frame is not None
frame has expected dimensions
frame has 2 or 3 dimensions
frame width > 0
frame height > 0
```

For RGB/BGR camera frames, expected shape is usually:

```text
(height, width, channels)
```

Example:

```text
(720, 1280, 3)
```

The exact frame size may differ from requested camera settings.  
If the actual resolution differs, this should initially be logged as a warning, not necessarily treated as fatal.

---

### 6.5 Runtime Camera Metadata

After a successful first frame, store metadata:

```json
{
  "camera": {
    "status": "OK",
    "device_index": 0,
    "backend": "opencv",
    "width": 1280,
    "height": 720,
    "channels": 3,
    "first_frame_timestamp": "...",
    "last_frame_timestamp": "...",
    "frames_read": 1
  }
}
```

Useful later:

- current FPS
- last frame age
- reconnect count
- failed read count
- selected backend
- device path if available

---

## 7. `INIT_CAM` State Lifecycle

### 7.1 `enter(ctx)`

Responsibilities:

- set current state to `INIT_CAM`
- set substate to `INIT_CAM_ENTER`
- reset camera initialization attempt counter
- publish UI status: “Initializing camera...”
- update health status
- log state entry

Example semantic behavior:

```python
def enter(self, ctx):
    ctx.runtime.current_state = "INIT_CAM"
    ctx.runtime.current_substate = "INIT_CAM_ENTER"
    ctx.health.update_state("INIT_CAM", "INIT_CAM_ENTER")
    ctx.ui.publish_status(
        state="INIT_CAM",
        substate="INIT_CAM_ENTER",
        message="Initializing camera..."
    )
    ctx.logger.info("[INIT_CAM] Entering INIT_CAM state")
```

---

### 7.2 `run(ctx)`

Responsibilities:

1. verify OpenCV
2. create/get camera service
3. attempt camera open/read
4. retry if necessary
5. update health and UI
6. transition to next state

Recommended run flow:

```text
INIT_CAM_ENTER
  ↓
INIT_CAM_CHECK_CV2
  ↓
INIT_CAM_CREATE_CAMERA_SERVICE
  ↓
INIT_CAM_OPEN_CAMERA
  ↓
INIT_CAM_READ_FIRST_FRAME
  ↓
INIT_CAM_VALIDATE_FRAME
  ↓
INIT_CAM_READY
  ↓
IDLE_NO_CARD
```

Failure flow:

```text
INIT_CAM_OPEN_CAMERA
  ↓
INIT_CAM_RETRY
  ↓
INIT_CAM_OPEN_CAMERA
  ↓
INIT_CAM_FAILED
  ↓
RECOVERY
```

Critical failure flow:

```text
INIT_CAM_CHECK_CV2
  ↓
ERROR_SAFE
```

---

### 7.3 `exit(ctx)`

Responsibilities:

- log state exit
- keep camera open if transitioning to `IDLE_NO_CARD`
- do not release the camera on success
- release camera only if transitioning to `RECOVERY` or `ERROR_SAFE`, depending on implementation policy
- publish transition status

Example:

```python
def exit(self, ctx):
    ctx.logger.info("[INIT_CAM] Leaving INIT_CAM state")
```

Important:

> On successful transition to `IDLE_NO_CARD`, the camera should remain available for subsequent states.

---

## 8. Internal Substates

Recommended internal substates:

```text
INIT_CAM_ENTER
INIT_CAM_CHECK_CV2
INIT_CAM_CREATE_CAMERA_SERVICE
INIT_CAM_OPEN_CAMERA
INIT_CAM_READ_FIRST_FRAME
INIT_CAM_VALIDATE_FRAME
INIT_CAM_RETRY
INIT_CAM_READY
INIT_CAM_FAILED
```

These do not need to be global state machine states.  
They should be visible in logs and health status.

---

## 9. Retry Policy

Camera initialization should use bounded retries.

Recommended MVP values:

```yaml
camera:
  init_retry_attempts: 3
  init_retry_delay_s: 0.5
```

Recommended behavior:

```text
attempt 1:
  open camera
  read frame
  validate frame
  success → IDLE_NO_CARD
  failure → log and retry

attempt 2:
  same

attempt 3:
  same

after final failure:
  transition to RECOVERY
```

Avoid:

- infinite retry loops inside `INIT_CAM`
- blocking the UI
- crashing the backend just because the camera is temporarily unavailable
- hiding the actual camera error

A bounded failure with visible UI status is better than silent suffering. The Jetson has enough thermals to worry about.

---

## 10. Recovery Policy

### 10.1 When to Transition to `RECOVERY`

Transition to `RECOVERY` if:

- camera cannot be opened after configured attempts
- camera opens but no valid frame can be read
- frame read repeatedly returns invalid frames
- camera backend reports runtime failure
- device exists but is busy or inaccessible

Examples:

```text
Camera device 0 could not be opened
First frame read failed
Frame is None
Frame has invalid shape
```

### 10.2 When to Transition to `ERROR_SAFE`

Transition to `ERROR_SAFE` if:

- OpenCV import fails
- camera config is structurally invalid
- required camera settings are missing
- code-level initialization failure makes recovery meaningless

Examples:

```text
ModuleNotFoundError: No module named 'cv2'
camera.device_index is missing
camera.init_retry_attempts is invalid
```

### 10.3 Recovery Should Own Reconnect Scheduling

`INIT_CAM` should not block forever.

If initialization fails repeatedly:

```text
INIT_CAM → RECOVERY
```

Then `RECOVERY` may decide:

```text
wait 2s → INIT_CAM
```

or:

```text
max recovery attempts exceeded → ERROR_SAFE
```

This keeps responsibilities clean.

---

## 11. Health Status Requirements

The health endpoint should show camera and OpenCV status during and after `INIT_CAM`.

Example during initialization:

```json
{
  "state": "INIT_CAM",
  "substate": "INIT_CAM_OPEN_CAMERA",
  "services": {
    "cv2": {
      "status": "OK",
      "version": "4.x"
    },
    "camera": {
      "status": "OPENING",
      "device_index": 0,
      "attempt": 1,
      "max_attempts": 3
    },
    "wled": {
      "status": "OPTIONAL_DISABLED"
    }
  }
}
```

Example after successful first frame:

```json
{
  "state": "INIT_CAM",
  "substate": "INIT_CAM_READY",
  "services": {
    "cv2": {
      "status": "OK",
      "version": "4.x"
    },
    "camera": {
      "status": "OK",
      "device_index": 0,
      "backend": "opencv",
      "width": 1280,
      "height": 720,
      "channels": 3,
      "frames_read": 1
    }
  },
  "next_state": "IDLE_NO_CARD"
}
```

Example after failure:

```json
{
  "state": "INIT_CAM",
  "substate": "INIT_CAM_FAILED",
  "services": {
    "camera": {
      "status": "ERROR",
      "device_index": 0,
      "attempts": 3,
      "last_error": "Camera device 0 could not be opened"
    }
  },
  "next_state": "RECOVERY"
}
```

---

## 12. UI Requirements During `INIT_CAM`

The UI should already be available because it was started in `BOOT`.

During `INIT_CAM`, the UI should show simple status messages.

### 12.1 Starting

```text
Initializing camera...
```

### 12.2 OpenCV OK

```text
OpenCV ready. Opening camera...
```

### 12.3 Camera Opening

```text
Opening camera device 0...
```

### 12.4 First Frame Read

```text
Reading first camera frame...
```

### 12.5 Success

```text
Camera ready. Waiting for card...
```

### 12.6 Failure / Retry

```text
Camera initialization failed. Retrying...
```

### 12.7 Recovery

```text
Camera unavailable. Entering recovery mode...
```

The UI should not require the browser to reload manually.

---

## 13. Logging Requirements

Every relevant step should be logged.

Recommended log events:

```text
[INIT_CAM] Entering INIT_CAM state
[INIT_CAM] Checking OpenCV import
[INIT_CAM] OpenCV available: version=<version>
[INIT_CAM] Creating CameraService
[INIT_CAM] Opening camera device <device_index>
[INIT_CAM] Camera initialization attempt <n>/<max>
[INIT_CAM] Camera opened successfully
[INIT_CAM] Reading first frame
[INIT_CAM] First frame valid: width=<w> height=<h> channels=<c>
[INIT_CAM] Transitioning to IDLE_NO_CARD
```

Failure logs:

```text
[INIT_CAM] Camera initialization attempt 1/3 failed: <error>
[INIT_CAM] Camera initialization failed after 3 attempts
[INIT_CAM] Transitioning to RECOVERY
```

OpenCV critical failure:

```text
[INIT_CAM] OpenCV import failed: <error>
[INIT_CAM] Transitioning to ERROR_SAFE
```

---

## 14. Configuration Requirements

Recommended config section:

```yaml
camera:
  init_in_boot: false
  preferred_backend: "opencv"
  device_index: 0
  width: 1280
  height: 720
  fps: 30

  open_timeout_s: 2.0
  read_timeout_s: 2.0

  init_retry_attempts: 3
  init_retry_delay_s: 0.5

  idle_poll_interval_s: 0.1

  allow_resolution_mismatch: true
  allow_fps_mismatch: true
```

Important:

```yaml
camera:
  init_in_boot: false
```

The camera must remain outside the `BOOT` state.

---

## 15. Data Structures

### 15.1 Camera Status

Recommended dataclass:

```python
@dataclass
class CameraStatus:
    status: str
    device_index: int | None = None
    backend: str = "opencv"
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    fps_requested: float | None = None
    fps_reported: float | None = None
    frames_read: int = 0
    last_frame_timestamp: float | None = None
    last_error: str | None = None
```

Status values:

```text
NOT_INITIALIZED
OPENING
OK
ERROR
RETRYING
DEGRADED
```

---

### 15.2 OpenCV Status

Recommended dataclass:

```python
@dataclass
class Cv2Status:
    status: str
    version: str | None = None
    last_error: str | None = None
```

Status values:

```text
NOT_CHECKED
OK
ERROR
```

---

### 15.3 Init Result

Recommended dataclass:

```python
@dataclass
class CameraInitResult:
    ok: bool
    frame: Any | None = None
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    error: str | None = None
```

---

## 16. `CameraService` Responsibilities

The `CameraService` should provide a small API.

Recommended methods:

```python
class CameraService:
    def probe_cv2(self) -> Cv2Status:
        ...

    def open(self) -> None:
        ...

    def read_frame(self) -> tuple[bool, Any | None]:
        ...

    def read_first_valid_frame(self) -> CameraInitResult:
        ...

    def is_opened(self) -> bool:
        ...

    def close(self) -> None:
        ...

    def get_status(self) -> CameraStatus:
        ...
```

MVP implementation should stay simple.

Do not add advanced camera backends until the basic OpenCV path works reliably.

---

## 17. Pseudocode

### 17.1 `InitCamState`

```python
class InitCamState:
    name = "INIT_CAM"

    def enter(self, ctx):
        ctx.runtime.current_state = "INIT_CAM"
        ctx.runtime.current_substate = "INIT_CAM_ENTER"
        ctx.health.update_state("INIT_CAM", "INIT_CAM_ENTER")
        ctx.ui.publish_status(
            state="INIT_CAM",
            substate="INIT_CAM_ENTER",
            message="Initializing camera..."
        )
        ctx.logger.info("[INIT_CAM] Entering INIT_CAM state")

    def run(self, ctx):
        ctx.runtime.current_substate = "INIT_CAM_CHECK_CV2"
        cv2_status = ctx.camera_service.probe_cv2()
        ctx.health.update_service("cv2", cv2_status)

        if cv2_status.status != "OK":
            ctx.runtime.last_error = cv2_status.last_error
            return "ERROR_SAFE"

        max_attempts = ctx.config.camera.init_retry_attempts

        for attempt in range(1, max_attempts + 1):
            ctx.runtime.current_substate = "INIT_CAM_OPEN_CAMERA"
            ctx.health.update_camera_attempt(attempt, max_attempts)
            ctx.ui.publish_status(
                state="INIT_CAM",
                substate="INIT_CAM_OPEN_CAMERA",
                message=f"Opening camera, attempt {attempt}/{max_attempts}"
            )

            try:
                ctx.camera_service.open()
                result = ctx.camera_service.read_first_valid_frame()

                if result.ok:
                    ctx.health.update_service("camera", ctx.camera_service.get_status())
                    ctx.ui.publish_status(
                        state="INIT_CAM",
                        substate="INIT_CAM_READY",
                        message="Camera ready. Waiting for card..."
                    )
                    return "IDLE_NO_CARD"

                raise RuntimeError(result.error or "First frame invalid")

            except Exception as exc:
                ctx.logger.warning(
                    "[INIT_CAM] Camera initialization attempt %s/%s failed: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                ctx.runtime.last_error = str(exc)
                ctx.health.update_camera_error(str(exc))
                ctx.camera_service.close()

                if attempt < max_attempts:
                    sleep(ctx.config.camera.init_retry_delay_s)

        ctx.ui.publish_status(
            state="INIT_CAM",
            substate="INIT_CAM_FAILED",
            message="Camera unavailable. Entering recovery mode..."
        )
        return "RECOVERY"

    def exit(self, ctx):
        ctx.logger.info("[INIT_CAM] Leaving INIT_CAM state")
```

---

## 18. Transition Rules

### 18.1 Success

```text
INIT_CAM → IDLE_NO_CARD
```

Condition:

```text
cv2 OK
camera opened
first frame valid
```

### 18.2 Recoverable Failure

```text
INIT_CAM → RECOVERY
```

Condition:

```text
camera failed after bounded retry attempts
```

### 18.3 Critical Failure

```text
INIT_CAM → ERROR_SAFE
```

Condition:

```text
cv2 import unavailable
invalid camera config
non-recoverable runtime setup error
```

---

## 19. Interaction with `IDLE_NO_CARD`

After `INIT_CAM` succeeds, `IDLE_NO_CARD` becomes responsible for maintaining a running idle loop.

`IDLE_NO_CARD` should:

- keep backend alive
- keep UI available
- monitor camera health
- periodically read frames or check stream availability
- wait for card detection logic to be introduced later

`INIT_CAM` only proves that the camera can produce valid frames.  
It does not continuously process frames.

---

## 20. Manual Test Plan

### Test 1: Start Backend and Observe `INIT_CAM`

Command:

```bash
cd /opt/cv-card-demo
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT completes
INIT_CAM starts
cv2 is checked
camera device is opened
first valid frame is read
IDLE_NO_CARD is reached
IDLE_NO_CARD remains active
```

Status:

```text
IN_PROGRESS
```

---

### Test 2: Verify Health Endpoint

Command:

```bash
curl http://localhost:8000/api/health
```

Expected result during or after init:

```text
JSON contains:
- state
- substate
- cv2 status
- camera status
- last error if present
```

Expected successful result:

```text
state is INIT_CAM or IDLE_NO_CARD
camera status is OK
cv2 status is OK
```

---

### Test 3: Camera Missing / Wrong Device Index

Config:

```yaml
camera:
  device_index: 99
```

Command:

```bash
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT completes
INIT_CAM starts
camera open fails with bounded retries
state transitions to RECOVERY
UI shows camera unavailable
health endpoint shows camera error
```

---

### Test 4: OpenCV Missing

This should not normally be performed on the main Jetson environment unless using a temporary test venv.

Expected result:

```text
INIT_CAM detects missing cv2
state transitions to ERROR_SAFE
UI shows critical OpenCV error
health endpoint shows cv2 ERROR
```

---

### Test 5: Valid USB Camera

Use a known working camera.

Command:

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
configured camera opens
first frame is valid
IDLE_NO_CARD is reached
```

If `v4l2-ctl` is not installed, the test can still proceed with `/dev/video*` and OpenCV.

---

## 21. Acceptance Criteria

`INIT_CAM` is complete when:

- [ ] `INIT_CAM` is entered after `BOOT`
- [ ] OpenCV availability is checked in `INIT_CAM`
- [ ] camera open/read flow works with a valid device
- [ ] first frame is validated
- [ ] camera metadata is stored in health status
- [ ] UI receives camera initialization status
- [ ] `IDLE_NO_CARD` is reached when the first frame is valid
- [ ] repeated camera failures transition to `RECOVERY`
- [ ] critical OpenCV/config errors transition to `ERROR_SAFE`
- [ ] manual test steps are documented
- [ ] known camera issues are recorded in `errors_and_fixes.md`
- [ ] global checklist is updated

---

## 22. Documentation Updates Required

When finishing this phase, update:

```text
docs/sub-sprint-phase/02_init_cam/checklist.md
docs/sub-sprint-phase/02_init_cam/errors_and_fixes.md
docs/global_checklist.md
```

Recommended checklist changes once stable:

```text
02 Init Camera → DONE
Camera opens successfully → checked
OpenCV reads valid frames → checked
```

Do not mark the phase as `DONE` until camera behavior is verified on the target Jetson or an explicitly accepted test camera setup.

---

## 23. Known Issues to Keep Visible

### 23.1 `/dev/video0` unavailable

Documented behavior:

```text
Camera device 0 could not be opened
```

Expected handling:

```text
bounded retries
transition to RECOVERY
visible health error
visible UI status
```

### 23.2 `IDLE_NO_CARD` persistence

Previously, `IDLE_NO_CARD` exited immediately after entry.

Expected behavior now:

```text
IDLE_NO_CARD remains active
backend stays alive
UI stays available
camera health is still monitored
```

### 23.3 Uvicorn compatibility issue

Already fixed.

This was a `BOOT`/UI-service issue but remains relevant because it affected reaching `INIT_CAM`.

---

## 24. Recommended Next Implementation Steps

1. Ensure `INIT_CAM` updates health status at every internal substate.
2. Ensure camera failure transitions to `RECOVERY`.
3. Verify `IDLE_NO_CARD` remains active after successful camera initialization.
4. Add or verify `/api/health` camera fields.
5. Test with the actual Jetson camera device.
6. Update phase checklist and error log.
7. Continue with `IDLE_NO_CARD` and card detection.

---

## 25. Final Summary

`INIT_CAM` should be a focused, deterministic camera initialization state.

It should answer exactly one question:

```text
Can this application access OpenCV and read a valid frame from the configured camera?
```

If yes:

```text
INIT_CAM → IDLE_NO_CARD
```

If the camera is temporarily unavailable:

```text
INIT_CAM → RECOVERY
```

If OpenCV or configuration is fundamentally broken:

```text
INIT_CAM → ERROR_SAFE
```

Everything else belongs to later phases.

The state should be boring, predictable, logged, and visible in the UI.  
In embedded demos, “boring” is not an insult. It is a survival strategy.
