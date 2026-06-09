# systemd Units — `systemd/`

*Applies to systemd unit files under `systemd/`. Loaded automatically here.*

## Goal

The demo must start automatically after the Jetson boots and recover from
crashes. Use systemd for process supervision.

## Services

```text
cv-card-demo.target
cv-card-demo-backend.service
cv-card-demo-kiosk.service
```

## Backend Service

- run from `/opt/cv-card-demo`
- activate the virtual environment
- pass the config path
- use `Restart=always`
- log to the journal
- fail clearly if config or venv is missing

## Kiosk Service

- open `http://localhost:8000`
- run in kiosk / fullscreen mode
- restart if the browser crashes
- must **not** kill the backend if the browser fails

## Avoid

Do not create: complex boot scripts launching many background processes,
unmanaged daemons, hidden `nohup` processes, or manual startup steps required for
normal operation.

## Debug Commands (document these)

```bash
systemctl status cv-card-demo-backend.service
systemctl status cv-card-demo-kiosk.service
journalctl -u cv-card-demo-backend.service -f
journalctl -u cv-card-demo-kiosk.service -f
```

## Deployment Principle

The deployment path should be boring and reproducible. Boring deployment is good
deployment.
