---
applyTo: "app/states/boot.py,app/states/init_cam.py,app/services/camera_service.py"
---

# BOOT and INIT_CAM Instructions

## BOOT State

BOOT is the first application state.

### BOOT Must Do

- load configuration
- validate configuration
- initialize logging
- create runtime context
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

BOOT succeeds if:

```text
config OK
logging OK
AppContext OK
UI service OK
health service OK
state machine OK
```

### BOOT Failure Criteria

BOOT fails if:

```text
config missing
config invalid
logging impossible
UI service cannot start
health endpoint unavailable
state machine cannot be created
```

WLED failure is not a BOOT failure.

## INIT_CAM State

INIT_CAM is responsible for camera and OpenCV initialization.

### INIT_CAM Must Do

- verify `cv2` import
- create camera service
- open configured camera
- read first valid frame
- verify frame shape
- optionally check requested FPS/resolution
- update UI and health status
- transition to next state on success

### INIT_CAM Failure Handling

On camera failure:

```text
INIT_CAM → RECOVERY
```

or, if unrecoverable:

```text
INIT_CAM → ERROR_SAFE
```

### Camera Retry Policy

Use bounded retry attempts.

Do not block forever in camera initialization.

Recommended behavior:

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

## UI During INIT_CAM

The UI should already be visible before the camera is opened.

On camera initialization:

```text
Initializing camera...
```

On camera failure:

```text
Camera could not be opened. Retrying...
```

## OpenCV Scope

Keep OpenCV initialization simple.

Do not introduce deep learning in INIT_CAM.

Deep learning is optional and later.
