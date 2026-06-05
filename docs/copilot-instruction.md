# CV-Card-Demo – Copilot Instruction Root

This file is the human-readable root instruction document for the CV-Card-Demo project.

For GitHub Copilot / VS Code, the primary repository instruction file is:

```text
.github/copilot-instructions.md
```

Additional targeted instruction files are stored in:

```text
.github/instructions/
```

Prompt templates for agentic work in VS Code are stored in:

```text
.github/prompts/
```

---

## Project Summary

CV-Card-Demo is a small computer-vision demo for a trade-fair booth.

Visitors place a business card or similar flat card on a table.  
A top-down RGB camera detects the card, estimates its simplified 2D pose on the table plane, and maps the horizontal card position to a normalized scalar value.

The normalized value is used to drive:

1. a live ranking/progress bar on a display
2. later, optionally, a 60-segment LED strip controlled by ESP32/WLED

---

## Critical Project Constraint

This project is a **demo**, not a production-grade industrial system.

Therefore:

- minimize development effort
- minimize dependencies
- minimize architectural complexity
- prefer robust simple code over clever abstractions
- prefer classical CV before deep learning
- avoid building generic frameworks
- avoid features that are not needed for the booth demo

When in doubt, choose the smallest solution that is stable, understandable, and testable.

---

## MVP Goal

The MVP is successful when:

1. the Jetson boots
2. the backend starts automatically
3. the UI opens automatically in kiosk mode
4. the camera initializes
5. OpenCV can read frames
6. a card can be detected on the table
7. the card's horizontal position is mapped to `0.0 ... 1.0`
8. the UI ranking bar updates live
9. backend crashes are recovered by systemd
10. WLED remains optional and must not block the demo

---

## Target Hardware

- NVIDIA Jetson Orin NX
- Ubuntu 22.04.5 LTS
- JetPack 6.1
- Jetson Linux R36.4.x
- ARMv8 / aarch64
- Top-down RGB camera
- Optional later: ESP32 with WLED and 60 LEDs

---

## Primary Software Stack

Use:

- Python 3
- OpenCV / `cv2`
- NumPy
- FastAPI
- WebSockets
- YAML
- systemd
- simple HTML/CSS/JavaScript

Avoid unless explicitly requested:

- ROS2
- Docker Compose
- Kubernetes
- cloud backends
- databases
- message brokers
- complex frontend frameworks
- deep-learning pipelines
- user authentication
- multi-camera abstractions

---

## Main Architectural Principle

The MVP should consist of a local backend and a local browser UI.

```text
systemd
├── cv-card-demo-backend.service
└── cv-card-demo-kiosk.service
```

The backend contains:

```text
FastAPI server
State machine
Camera service
OpenCV pipeline
Score mapper
WebSocket publisher
Health service
optional WLED client
```

---

## Current Development Focus

The immediate focus is:

```text
BOOT → INIT_CAM
```

BOOT is responsible for:

- loading config
- initializing logging
- creating the app context
- starting the UI service
- starting health endpoints
- creating the state machine
- transitioning to INIT_CAM

INIT_CAM is responsible for:

- importing/checking OpenCV
- opening the camera
- reading first frames
- validating FPS and resolution
- handling reconnect/recovery

The BOOT state must not open the camera.

---

## WLED Policy

WLED is optional for now.

The MVP config should use:

```yaml
wled:
  enabled: false
```

Rule:

> WLED must never block BOOT, UI, camera initialization, or card detection.

Later, WLED can be added as a non-critical output channel.

---

## Coding Style

Write code that is:

- simple
- explicit
- typed where useful
- easy to log
- easy to test manually
- recoverable
- boring in the best possible way

Avoid:

- hidden global state
- silent exceptions
- infinite loops without timeout
- large monolithic files
- premature abstraction
- dependency-heavy implementations
- code that requires a PhD and a forgiveness ritual to debug

---

## Final Decision Rule

If a feature does not directly help the booth demo become more stable, visible, or easier to operate, do not implement it yet.
