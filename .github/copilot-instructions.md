# GitHub Copilot Instructions – CV-Card-Demo

## Assistant Role

You are assisting with the development of a small, robust computer-vision demo for a trade-fair booth.

The project is a **demo MVP**.
Always prefer simple, stable, locally runnable solutions over sophisticated architecture.

## Project in One Sentence

A top-down RGB camera detects a card on a table, maps its horizontal position to a normalized score `0.0 ... 1.0`, and displays the result in a live browser UI.

## Primary Goal

Build the smallest reliable system that can run unattended at a booth.

The priority order is:

1. boot reliably
2. show UI reliably
3. initialize camera reliably
4. detect a card reliably
5. map card position to score reliably
6. recover from crashes
7. add optional WLED output later

## Demo Scope

This is not a production system.

Do not introduce unnecessary systems, frameworks, protocols, or abstractions.
Keep the development effort minimal.

## Target Platform

The software runs locally on:

- NVIDIA Jetson Orin NX
- Ubuntu 22.04.5 LTS
- JetPack 6.1
- Jetson Linux R36.4.x
- ARMv8 / aarch64

## Preferred Stack

Use:

- Python 3
- OpenCV / `cv2`
- NumPy
- FastAPI
- WebSockets
- YAML
- systemd
- simple HTML/CSS/JavaScript

Use only if explicitly needed:

- GStreamer
- pypylon
- Ultralytics YOLO-seg
- ONNX
- TensorRT
- WLED JSON API

Avoid in the MVP:

- ROS2
- Docker Compose
- Kubernetes
- cloud APIs
- databases
- message brokers
- complex frontend frameworks
- training pipelines
- multi-camera abstractions
- authentication systems

## Architecture

The MVP is a local application with two systemd-managed processes:

```text
cv-card-demo-backend.service
cv-card-demo-kiosk.service
```

The backend process should contain:

```text
FastAPI web server
State machine
Camera service
CV pipeline
Score mapper
WebSocket publisher
Health service
optional WLED client
```

The browser kiosk displays the UI from:

```text
http://localhost:8000
```

## State Machine

Use a simple explicit state machine.

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

Each state transition must be logged.

## BOOT Rules

BOOT must:

- load config
- validate config
- initialize logging
- create AppContext
- start UI service
- start health service
- create state machine runtime
- transition to INIT_CAM

BOOT must not:

- open the camera
- run CV detection
- require WLED
- block on optional hardware

## INIT_CAM Rules

INIT_CAM must:

- verify `cv2` availability
- open the configured camera
- read first frames
- check frame validity
- validate basic resolution/FPS assumptions
- transition to the next state or recovery

## WLED Rules

WLED is optional for now.

If WLED is disabled or offline, the demo must still run.

Do not make WLED a critical dependency.

## Error Handling

Use pragmatic error handling:

- fail clearly
- log the reason
- update health status
- use recovery state where useful
- rely on systemd for process-level restart
- use timeouts for external resources

## Code Style

Prefer:

- small functions
- simple classes
- clear names
- type hints where useful
- dataclasses for structured data
- explicit configuration
- predictable control flow

Avoid:

- clever metaprogramming
- hidden side effects
- global mutable state
- broad `except Exception` without logging
- large one-file implementations
- speculative future-proofing

## Health and Debugging

Expose enough state to debug the booth setup:

- current app state
- current substate
- UI service status
- camera status
- OpenCV status
- last error
- uptime
- FPS once camera is active
- last score once tracking is active

## MVP Rule

If a change does not directly improve the booth demo's reliability, clarity, or visible functionality, postpone it.
