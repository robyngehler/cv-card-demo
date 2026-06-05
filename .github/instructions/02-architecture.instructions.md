---
applyTo: "app/**/*.py"
---

# Architecture Instructions

## System Architecture

The application should be a local single-machine system.

```text
systemd
├── cv-card-demo-backend.service
└── cv-card-demo-kiosk.service
```

## Backend Responsibilities

The backend process owns:

```text
FastAPI server
State machine
Camera service
CV pipeline
Score mapper
WebSocket publisher
Health service
optional WLED client
```

## Suggested Python Structure

```text
app/
├── main.py
├── config_loader.py
├── app_context.py
├── state_machine.py
├── states/
│   ├── boot.py
│   ├── init_cam.py
│   ├── calibration.py
│   ├── idle.py
│   ├── tracking.py
│   ├── recovery.py
│   └── error_safe.py
├── services/
│   ├── ui_service.py
│   ├── health_service.py
│   ├── camera_service.py
│   └── wled_client.py
├── cv/
│   ├── preprocessing.py
│   ├── classical_card_detector.py
│   ├── pose_estimator.py
│   └── score_mapper.py
└── web/
    ├── index.html
    ├── app.js
    └── styles.css
```

## AppContext

Use one central context object to pass runtime dependencies.

Example:

```python
@dataclass
class AppContext:
    config: AppConfig
    logger: logging.Logger
    runtime: RuntimeState
    services: ServiceRegistry
```

Avoid uncontrolled global state.

## Separation of Concerns

Keep these separate:

```text
state logic
camera IO
CV processing
score mapping
UI publishing
health reporting
configuration
```

## Main File

`main.py` should remain an orchestrator.

It should not contain:

- detailed CV algorithms
- large HTML strings
- camera-specific hacks
- state-specific business logic
- WLED protocol details

## Services

Each service should have one clear responsibility:

- `UiService`: HTTP, WebSocket, static UI
- `HealthService`: health state and health endpoint data
- `CameraService`: camera open/read/reconnect
- `ScoreMapper`: normalized score calculation
- `WledClient`: optional LED output

## Simplicity Rule

Do not create an abstraction unless there are at least two real implementations or it clearly improves testability.
