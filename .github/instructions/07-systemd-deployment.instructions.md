---
applyTo: "systemd/**,scripts/**/*.sh"
---

# systemd and Deployment Instructions

## Goal

The demo must start automatically after the Jetson boots and recover from crashes.

Use systemd for process supervision.

## Services

Use:

```text
cv-card-demo.target
cv-card-demo-backend.service
cv-card-demo-kiosk.service
```

## Backend Service

The backend service starts the Python app.

Expected behavior:

- run from `/opt/cv-card-demo`
- activate virtual environment
- pass config path
- use `Restart=always`
- log to journal
- fail clearly if config or venv is missing

## Kiosk Service

The kiosk service starts a local browser.

Expected behavior:

- open `http://localhost:8000`
- run in kiosk/fullscreen mode
- restart if browser crashes
- not kill backend if browser fails

## Shell Scripts

Shell scripts should use:

```bash
set -euo pipefail
```

Use `exec` when starting the final long-running process so systemd supervises the correct PID.

## Avoid

Do not create:

- complex boot scripts that launch many background processes
- unmanaged daemons
- hidden nohup processes
- manual startup steps required for normal operation

## Debug Commands

Useful commands should be documented:

```bash
systemctl status cv-card-demo-backend.service
systemctl status cv-card-demo-kiosk.service
journalctl -u cv-card-demo-backend.service -f
journalctl -u cv-card-demo-kiosk.service -f
```

## Deployment Principle

The deployment path should be boring and reproducible.

Boring deployment is good deployment.
