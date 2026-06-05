# CV-Card-Demo – BOOT-Step Specification (English)

**Project:** CV-Card-Demo
**Target platform:** NVIDIA Jetson Orin NX
**OS / Stack:** Ubuntu 22.04.5 LTS, JetPack 6.1, Jetson Linux R36.4.x
**Document status:** Draft for MVP boot architecture
**Focus:** Reliable startup of UI, backend, state machine and OpenCV/CV pipeline
**WLED:** Optional for MVP, may be added later

---

## Repository structure preparation

Before deployment on the Jetson, prepare the repository and target layout so systemd services, scripts and the Python app have predictable paths and permissions.

Recommended steps:

- Create the target base directory and set ownership to a service user (example `demo`):

  sudo mkdir -p /opt/cv-card-demo
  sudo chown -R demo:demo /opt/cv-card-demo

- Populate these subdirectories in the repo (or ensure they are created during install):
  - `app/` — Python package and application code
  - `config/` — `config.yaml` and example configs
  - `scripts/` — `run_backend.sh`, `run_kiosk.sh`, `preflight.sh`, `install_services.sh`
  - `systemd/` — service unit and target files to copy to `/etc/systemd/system/`
  - `logs/` — writable by service user
  - `venv/` — the virtualenv used on the device (or provide instructions to create it during install)

- Create a service user and group (if not present):

  sudo useradd --system --create-home --home-dir /home/demo demo
  sudo mkdir -p /home/demo
  sudo chown demo:demo /home/demo

- Prepare and test a Python virtual environment, install dependencies (including OpenCV), and verify `venv/bin/python` works.

- Ensure the repository contains a small `install_services.sh` that copies unit files from `systemd/` to `/etc/systemd/system/`, enables the `cv-card-demo.target` and reloads systemd.

- Ensure `scripts/*` are executable and owned by the service user.

- Provide a README or quick install guide with the exact commands to set up the device.

These steps make the rest of the BOOT flow deterministic and easier to automate.

---

## 1. Purpose of the BOOT step

The BOOT step describes the controlled startup of the demo application after system power-on.

Goals:

1. System boots automatically after power-on.
2. Backend application reliably starts.
3. Web UI is served and shown in kiosk mode.
4. The state machine starts cleanly in state `BOOT`.
5. The application transitions to `INIT_CAM` after a successful basic startup.
6. Camera/OpenCV connection is initialized in `INIT_CAM`.
7. Errors are detected, logged and do not cause uncontrolled crashes.
8. WLED/ESP32 is not critical for MVP and is optional.

The BOOT step should remain simple, robust and well debugable.

---

## 2. Scope: Linux boot vs application BOOT

There are two boot levels:

Power On
  ↓
Linux / systemd Boot
  ↓
Start cv-card-demo services
  ↓
Application BOOT state
  ↓
INIT_CAM

### 2.1 Linux / systemd Boot

This level is outside the Python app.

Responsibilities:

- OS boots.
- Network, graphical session and user environment are initialized.
- systemd starts required services.
- Backend service is started.
- Kiosk service is started.
- Services are restarted automatically if they crash.

### 2.2 Application BOOT state

This level is inside the Python app.

Responsibilities:

- Load and validate configuration.
- Initialize logging.
- Create application context.
- Provide webserver / UI service.
- Create the state machine.
- Initialize health status.
- Prepare optional WLED path (non-blocking).
- Trigger transition to `INIT_CAM` when ready.

---

## 3. MVP priorities

For the first stable MVP the following priority applies:

- Priority 1: Backend / main app — required
- Priority 2: State machine — required
- Priority 3: Config + logging — required
- Priority 4: UI server — required
- Priority 5: Browser / kiosk — required but separated from the backend
- Priority 6: Camera / OpenCV — initialized in `INIT_CAM`, not in BOOT
- Priority 7: WLED / ESP32 — optional

Important: WLED must not block BOOT for the MVP. The system must run fully with UI and CV pipeline even without an LED strip.

---

## 4. High-level start sequence

Power On
  ↓
Jetson boots Ubuntu
  ↓
systemd starts cv-card-demo-backend.service
  ↓
Backend runs Python main.py
  ↓
FastAPI / UI server is provided
  ↓
State machine starts in state BOOT
  ↓
BOOT checks config, logging, UI service, context
  ↓
systemd starts cv-card-demo-kiosk.service
  ↓
Browser opens local UI in fullscreen
  ↓
BOOT marks system READY_FOR_INIT_CAM
  ↓
Transition to INIT_CAM
  ↓
INIT_CAM opens camera and verifies cv2 connection

---

## 5. Recommended process architecture

Use two systemd services plus a target:

systemd
├── cv-card-demo.target
├── cv-card-demo-backend.service
└── cv-card-demo-kiosk.service

### 5.1 Backend service

Starts:

- Python app
- State machine
- FastAPI webserver
- WebSocket endpoints
- Health endpoints
- Later: CV pipeline
- Later: optional WLED client

### 5.2 Kiosk service

Starts:

- Local browser in fullscreen
- Displays local UI at `http://localhost:8000`

Separating backend and browser improves robustness and debugging.

---

## 6. Directory layout (recommended on Jetson)

/opt/cv-card-demo
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config_loader.py
│   ├── app_context.py
│   ├── state_machine.py
│   │
│   ├── states/
│   │   ├── __init__.py
│   │   ├── boot.py
│   │   ├── init_cam.py
│   │   ├── error_safe.py
│   │   └── recovery.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ui_service.py
│   │   ├── health_service.py
│   │   ├── camera_service.py
│   │   └── wled_client.py        # optional, later
│   │
│   ├── web/
│   │   ├── index.html
│   │   ├── app.js
│   │   └── styles.css
│   │
│   └── cv/
│       ├── __init__.py
│       # optional future camera abstraction package
│
├── config/
│   └── config.yaml
│
├── scripts/
│   ├── run_backend.sh
│   ├── run_kiosk.sh
│   ├── preflight.sh
│   └── install_services.sh
│
├── systemd/
│   ├── cv-card-demo.target
│   ├── cv-card-demo-backend.service
│   └── cv-card-demo-kiosk.service
│
├── logs/
│   └── app.log
│
└── venv/

---

## 7. systemd components

### 7.1 Target: `cv-card-demo.target`

Path: `/etc/systemd/system/cv-card-demo.target`

Unit example:

[Unit]
Description=CV Card Demo Application Stack
Wants=cv-card-demo-backend.service cv-card-demo-kiosk.service
After=network-online.target graphical.target

[Install]
WantedBy=multi-user.target

Purpose: group backend and kiosk so the whole application can be started/stopped together.

Examples:

sudo systemctl start cv-card-demo.target
sudo systemctl stop cv-card-demo.target
sudo systemctl restart cv-card-demo.target

### 7.2 Backend service: `cv-card-demo-backend.service`

Path: `/etc/systemd/system/cv-card-demo-backend.service`

Unit example:

[Unit]
Description=CV Card Demo Backend and State Machine
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=10

[Service]
Type=simple
User=demo
Group=demo
WorkingDirectory=/opt/cv-card-demo

Environment=PYTHONUNBUFFERED=1
Environment=CV_CARD_DEMO_CONFIG=/opt/cv-card-demo/config/config.yaml

ExecStart=/opt/cv-card-demo/scripts/run_backend.sh

Restart=always
RestartSec=2

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

Notes:

- `Restart=always` ensures systemd restarts after a crash.
- `RestartSec=2` prevents rapid restart loops.
- Logs go to the systemd journal. Use a dedicated `demo` user.

### 7.3 Kiosk service: `cv-card-demo-kiosk.service`

Path: `/etc/systemd/system/cv-card-demo-kiosk.service`

Unit example:

[Unit]
Description=CV Card Demo Local Kiosk Browser
After=graphical.target cv-card-demo-backend.service
Wants=cv-card-demo-backend.service

[Service]
Type=simple
User=demo
Group=demo

Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/demo/.Xauthority

ExecStart=/opt/cv-card-demo/scripts/run_kiosk.sh

Restart=always
RestartSec=3

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target

Notes: the Kiosk depends on the graphical session and is separate from the backend.

---

## 8. Startup scripts

### 8.1 `run_backend.sh`

Path: `/opt/cv-card-demo/scripts/run_backend.sh`

Script behavior:

- Change to app dir.
- Verify virtualenv exists and activate it.
- Check `config.yaml` exists.
- Exec the Python app so systemd monitors the real process.

Example (kept in repo `scripts/`):

#!/usr/bin/env bash
set -euo pipefail

cd /opt/cv-card-demo

if [ ! -d "/opt/cv-card-demo/venv" ]; then
  echo "ERROR: Python virtual environment not found at /opt/cv-card-demo/venv"
  exit 1
fi

source /opt/cv-card-demo/venv/bin/activate

CONFIG_PATH="${CV_CARD_DEMO_CONFIG:-/opt/cv-card-demo/config/config.yaml}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: Config file not found: $CONFIG_PATH"
  exit 1
fi

exec python -m app.main \
  --config "$CONFIG_PATH" \
  --initial-state BOOT

### 8.2 `run_kiosk.sh`

Path: `/opt/cv-card-demo/scripts/run_kiosk.sh`

Script behavior:

- Check backend health briefly (non-blocking).
- Select an available browser executable.
- Launch browser in kiosk mode to `http://localhost:8000` with flags to reduce dialogs.
- Exec the browser process so systemd supervises it.

### 8.3 `preflight.sh`

Path: `/opt/cv-card-demo/scripts/preflight.sh`

Purpose:

- Check app dir, config, venv and python executable.
- Verify OpenCV import.
- Check port 8000 availability.
- List available video devices.
- Check display environment.

Example checks include verifying `cv2` import from the venv and printing device nodes under `/dev/video*`.

---

## 9. Application BOOT state

The BOOT state is the first state of the internal state machine.

### 9.1 Goal

Ensure base application services are available. BOOT checks:

- Config loaded and valid
- Logging initialized
- AppContext created
- UI service available
- Health service available
- State machine available
- WLED optional and non-blocking

The camera is not opened in BOOT; camera initialization happens in `INIT_CAM`.

### 9.2 Entry conditions

The BOOT state is entered when:

- `main.py` started successfully
- Config path provided
- `initial_state == BOOT`

### 9.3 Exit conditions

Allowed to transition to `INIT_CAM` when:

- Config OK
- Logging OK
- AppContext OK
- UI-Service OK
- Health-Service OK
- State Machine OK

WLED is not required.

### 9.4 Error conditions

BOOT transitions to `ERROR_SAFE` if:

- Config missing or invalid
- Logging cannot be initialized
- UI-Service cannot start
- Webserver port unavailable
- State Machine cannot be created
- Critical Python import missing

---

## 10. BOOT internal substates

Possible internal substates (visible in health and logs):

BOOT_ENTER
BOOT_LOAD_CONFIG
BOOT_VALIDATE_CONFIG
BOOT_INIT_LOGGING
BOOT_CREATE_CONTEXT
BOOT_START_UI_SERVICE
BOOT_INIT_HEALTH_SERVICE
BOOT_OPTIONAL_WLED_PREPARE
BOOT_READY

These can be surfaced in the health endpoint and WebSocket messages.

---

## 11. BOOT flow details

### 11.1 `BOOT_ENTER`

- Set state to `BOOT`
- Save timestamp and increment boot attempt counter
- Prepare UI status

Health example:

{"state": "BOOT", "substate": "BOOT_ENTER", "message": "Application boot started"}

### 11.2 `BOOT_LOAD_CONFIG`

- Load the config file
- Check required fields and apply defaults

Required config sections for MVP: `app`, `server`, `boot`, `camera`, `logging`.

### 11.3 `BOOT_VALIDATE_CONFIG`

- Validate port numbers, camera config, paths and booleans
- Minimal validated sample fields are provided in the example config below

### 11.4 `BOOT_INIT_LOGGING`

- Enable console logging and file logging if possible
- Set log level from config
- Generate a boot ID and write initial status
- If file logging fails but console logging works, continue with a warning; if no logging at all, go to `ERROR_SAFE`

### 11.5 `BOOT_CREATE_CONTEXT`

Create an `AppContext` holding config, logger, runtime data (boot_id, start_time, current_state, degraded_flags), services (ui, health, camera, optional wled) and state data.

### 11.6 `BOOT_START_UI_SERVICE`

Start the FastAPI app, mount static UI files and register health and WebSocket endpoints. Recommended endpoints:

GET  /
GET  /api/health
GET  /api/state
GET  /api/version
WS   /ws/status
WS   /ws/score

The UI should show basic boot status messages and final message "Ready for camera initialization" (camera is initialized in `INIT_CAM`).

### 11.7 `BOOT_INIT_HEALTH_SERVICE`

Provide a minimal `/api/health` response describing app, version, state, substate, uptime and per-service status (ui, camera, cv2, wled). Example statuses: `OK`, `NOT_INITIALIZED`, `OPTIONAL_DISABLED`.

### 11.8 `BOOT_OPTIONAL_WLED_PREPARE`

If `wled.enabled` is false, set WLED status to `OPTIONAL_DISABLED`. If enabled, create a client object but do not block boot; any probing must be optional and non-blocking.

### 11.9 `BOOT_READY`

When all critical components are OK, publish a system status message and transition to `INIT_CAM`.

Example message:

{"type": "system_status", "state": "BOOT", "substate": "BOOT_READY", "message": "Boot complete. Transitioning to INIT_CAM."}

---

## 12. Transition to INIT_CAM

Transition happens automatically from `BOOT_READY` to `INIT_CAM`. `INIT_CAM` then:

- Checks `import cv2`
- Selects camera backend
- Opens the camera and reads initial frames
- Validates FPS and resolution
- Sets camera parameters if needed
- On success transitions to `CALIBRATION` or `IDLE_NO_CARD`

BOOT deliberately does not verify the camera connection itself to keep boot fast and robust.

---

## 13. Where to check OpenCV / camera

Responsibility table:

- `import cv2` check: optional in `preflight.sh`, required in `INIT_CAM`
- Camera device present: optional in `preflight.sh`, final check in `INIT_CAM`
- Camera open/read/frames: `INIT_CAM`
- FPS/resolution: `INIT_CAM`

This keeps camera errors scoped to `INIT_CAM` and shows the UI even when the camera fails.

---

## 14. Error and recovery strategy in BOOT

Critical errors → `ERROR_SAFE` or process exit (systemd will restart): missing config, invalid config, required params missing, UI port blocked, UI-service cannot start, AppContext/state machine cannot be initialized.

Non-critical errors: WLED disabled/unreachable, browser not connected yet, camera not initialized.

Browser errors: backend continues running; kiosk service is restarted by systemd and logged.

UI-service errors: BOOT fails and transitions to `ERROR_SAFE`; systemd restarts the backend.

---

## 15. Health status model

Service status values: `OK`, `WARN`, `ERROR`, `NOT_INITIALIZED`, `NOT_CHECKED`, `OPTIONAL_DISABLED`, `DEGRADED`.

Example `/api/health` during BOOT is provided in the original spec.

---

## 16. WebSocket status model

During BOOT the backend sends status messages to the UI via WebSocket, for example indicating current substate and messages like "Loading configuration" or "Boot complete" and the subsequent `INIT_CAM` messages.

---

## 17. Example config for MVP

Path: `/opt/cv-card-demo/config/config.yaml`

Example content:

app:
  name: "cv-card-demo"
  version: "0.1.0"
  initial_state: "BOOT"

server:
  host: "0.0.0.0"
  port: 8000
  ui_static_dir: "/opt/cv-card-demo/app/web"

boot:
  next_state: "INIT_CAM"
  max_boot_duration_s: 10
  allow_degraded_wled: true

logging:
  level: "INFO"
  file: "/opt/cv-card-demo/logs/app.log"
  log_to_console: true
  log_to_file: true

camera:
  init_in_boot: false
  preferred_backend: "opencv"
  device_index: 0
  width: 1280
  height: 720
  fps: 30

wled:
  enabled: false
  host: ""
  timeout_ms: 300
  fail_mode: "optional"

---

## 18. Python app: semantic structure

`main.py` should:

- Parse CLI args (config path, initial state)
- Load raw config and initialize logger
- Create `AppContext`
- Create and attach state machine to context
- Start the state machine with the requested initial state

Example snippet:

```python
def main():
    args = parse_args()

    raw_config = load_config(args.config)
    logger = init_basic_logger(raw_config)

    ctx = create_app_context(
        config=raw_config,
        logger=logger,
    )

    state_machine = create_state_machine(ctx)
    ctx.state_machine = state_machine

    state_machine.start(initial_state=args.initial_state)
```

---

End of English BOOT specification.
