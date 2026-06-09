# Architecture — `app/`

*Applies to all Python code under `app/`. Loaded automatically when you work here.*

## System Architecture

The application is a local single-machine system.

```text
systemd
├── cv-card-demo-backend.service
└── cv-card-demo-kiosk.service
```

## Backend Responsibilities

```text
FastAPI server (UiService)
State machine
Camera pipeline (CameraService + CameraControlService)
CV pipeline (detector → tracker → fusion → score)
Snapshot pipeline (precheck → capture → OCR → identity → persist → embed)
WebSocket publisher
Health service
Questionnaire service
optional WLED client
```

## Actual Python Structure

```text
app/
├── main.py                     — orchestrator; registers all services
├── config_loader.py
├── app_context.py              — AppContext dataclass
├── state_machine.py
├── logging_setup.py
├── states/
│   ├── boot.py
│   ├── init_cam.py
│   ├── calibration.py
│   ├── idle.py
│   ├── candidate_detected.py
│   ├── tracking.py
│   ├── snapshot.py             — snapshot capture + post-processing trigger
│   ├── recovery.py
│   └── error_safe.py
├── services/                   — 17 service modules (see app/services/CLAUDE.md)
├── cv/                         — detection + tracking modules (see app/cv/CLAUDE.md)
├── utils/
└── web/                        — HTML/CSS/JS UI (see app/web/CLAUDE.md)
```

## AppContext

One central context object for all runtime dependencies:

```python
@dataclass
class AppContext:
    config: AppConfig
    logger: logging.Logger
    runtime: RuntimeState
    services: ServiceRegistry
```

## Separation of Concerns

Keep separate: state logic, camera IO, CV processing, score mapping, snapshot
pipeline, UI publishing, health reporting, configuration.

## Main File

`main.py` registers all services and starts the state machine. It must **not**
contain CV algorithms, state business logic, or protocol details.

## Simplicity Rule

Do not create an abstraction unless there are at least two real implementations
or it clearly improves testability.
