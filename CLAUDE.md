# CV-Card-Demo — Claude Code Project Memory

## Your Role

You are Claude Code, assisting with a small, robust computer-vision demo for a
trade-fair booth.

This is a **demo MVP**. Always prefer simple, stable, locally runnable solutions
over sophisticated architecture.

## Project in One Sentence

A top-down RGB camera detects a card on a table, maps its horizontal position to
a normalized score `0.0 ... 1.0`, and displays the result in a live browser UI.

```text
camera frame
  ↓
OpenCV card detection
  ↓
card center x-position
  ↓
normalized score 0.0 ... 1.0
  ↓
browser UI ranking bar
```

A visitor places a business card (or similar card) on a table. A fixed top-down
camera detects it. The horizontal card position controls a live ranking/progress
bar in the browser.

## Primary Goal

Build the smallest reliable system that can run unattended at a booth.

Priority order:

1. boot reliably
2. show UI reliably
3. initialize camera reliably
4. detect a card reliably
5. map card position to score reliably
6. recover from crashes
7. add optional WLED output later

## Decision Rule

If there are multiple valid implementations, choose the simplest one that is
stable and easy to debug. If a change does not directly improve the booth demo's
reliability, clarity, or visible functionality, postpone it.

Always minimize: development time, dependency count, deployment complexity,
maintenance burden, hardware assumptions.

## Demo Scope / Non-Goals

This is a demo, not a production system. Do not introduce unnecessary systems,
frameworks, protocols, or abstractions.

Do **not** implement these unless explicitly requested:

- ROS2 integration
- Docker Compose / Kubernetes / container orchestration
- cloud services / cloud APIs
- databases / message brokers
- user accounts / authentication
- multi-camera support / multi-camera abstractions
- ML training pipeline
- complex frontend frameworks (React/Vue/Svelte) or build tools
- production monitoring stack
- generic plugin architecture

## Target Platform

The software runs locally on:

- NVIDIA Jetson Orin NX
- Ubuntu 22.04.5 LTS
- JetPack 6.1
- Jetson Linux R36.4.x
- ARMv8 / aarch64

The Jetson is the deployment target, but development code should stay as portable
as reasonably possible. Do not hard-code Jetson-specific paths unless they are
deployment scripts or documented configuration defaults.

### Camera assumptions

- one top-down RGB camera, fixed above the table
- the workspace is planar
- lighting is stable, table background is controlled
- only one main card is expected in the active workspace

### Optional LED setup (later)

- ESP32 + WLED + 60 LEDs over HTTP/JSON
- not required for the MVP

## Preferred Stack

Use: Python 3, OpenCV / `cv2`, NumPy, FastAPI, WebSockets, YAML, systemd, simple
HTML/CSS/JavaScript.

Use only if explicitly needed: GStreamer, pypylon, Ultralytics YOLO-seg, ONNX,
TensorRT, WLED JSON API.

Avoid in the MVP: ROS2, Docker Compose, Kubernetes, cloud APIs, databases,
message brokers, complex frontend frameworks, training pipelines, multi-camera
abstractions, authentication systems.

## Architecture (overview)

Local single-machine system with two systemd-managed processes:

```text
cv-card-demo-backend.service
cv-card-demo-kiosk.service
```

The backend contains: FastAPI server, state machine, camera pipeline, CV
pipeline (classical/YOLO detector + card tracker + hand-presence fusion),
snapshot pipeline (precheck → capture → OCR → identity → SQLite persistence →
Qdrant vector embedding), questionnaire service, WebSocket publisher, health
service, optional WLED client. The browser kiosk displays the UI from
`http://localhost:8000`.

The system has grown beyond the initial MVP scope to include: PaddleOCR,
identity resolution, SQLite persistence, Qdrant vector embeddings,
questionnaire flow, and multi-view browser UI. The MVP simplicity rule still
applies to new changes — do not add further complexity unless it directly
serves the booth demo.

Detailed architecture lives in `app/CLAUDE.md` (loaded automatically when you work
under `app/`).

## State Machine (overview)

Simple, explicit state machine. Known states:

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

Every state transition must be logged. Details in `app/states/CLAUDE.md`.

## Error Handling

Pragmatic error handling:

- fail clearly, log the reason
- update health status
- use the recovery state where useful
- rely on systemd for process-level restart
- use timeouts for external resources

Avoid broad `except Exception` without logging.

## Code Style

Prefer: small functions, simple classes, clear names, type hints where useful,
dataclasses for structured data, explicit configuration, predictable control flow.

Avoid: clever metaprogramming, hidden side effects, global mutable state, broad
silent exception handling, large one-file implementations, speculative
future-proofing.

Do not create an abstraction unless there are at least two real implementations
or it clearly improves testability.

## Health and Debugging

Expose enough state to debug the booth setup: current app state, current substate,
UI service status, camera status, OpenCV status, last error, uptime, FPS once the
camera is active, last score once tracking is active.

## Documentation Rule (cross-cutting)

This repo keeps lightweight progress/error documentation. When you change
implementation code, also check whether one of these needs an update:

```text
docs/global_checklist.md
docs/sub-sprint-phase/<phase>/checklist.md
docs/sub-sprint-phase/<phase>/errors_and_fixes.md
```

Full rules and structure: `docs/CLAUDE.md`.

## How This Project Memory Is Organized (Claude Code specifics)

- This root `CLAUDE.md` is always in context: it holds the cross-cutting rules
  (scope, platform, stack, error handling, code style, docs rule).
- Directory-scoped rules live in nested `CLAUDE.md` files and load automatically
  when you read or edit files in that subtree:
  - `app/CLAUDE.md` — architecture
  - `app/states/CLAUDE.md` — state machine + BOOT / INIT_CAM
  - `app/cv/CLAUDE.md` — CV pipeline
  - `app/services/CLAUDE.md` — camera / UI / WLED services
  - `app/web/CLAUDE.md` — browser UI
  - `config/CLAUDE.md` — config & WLED defaults
  - `systemd/CLAUDE.md` — service units
  - `scripts/CLAUDE.md` — shell scripts
  - `docs/CLAUDE.md` — progress documentation
- Reusable task prompts are project slash commands under `.claude/commands/`:
  - `/implement-next-state <STATE_NAME>` — implement one state machine state
  - `/debug-runtime-issue` — analyze a runtime failure, propose the smallest fix
  - `/create-minimal-test` — add the smallest useful test for a module
  - `/refactor-with-mvp-scope` — refactor while preserving MVP scope

## MVP Rule

If a change does not directly improve the booth demo's reliability, clarity, or
visible functionality, postpone it. This is a demo. Keep it boring and stable.
