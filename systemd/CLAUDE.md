# systemd Units — `systemd/`

*Applies to systemd unit files under `systemd/`. Loaded automatically here.*

## Goal

The demo must start automatically after the Jetson boots and recover from
crashes. Use systemd for process supervision.

## Services

```text
cv-card-demo.target
cv-card-demo-backend.service.in   (template)
cv-card-demo-kiosk.service.in     (template)
```

The `.service.in` files are **templates** with `@ROOT@`, `@USER@`, `@GROUP@`,
`@DISPLAY@`, `@XAUTHORITY@` placeholders. `scripts/install_services.sh` renders
them for the current checkout (path + user auto-detected, env-overridable) and
installs the rendered `.service` files into `/etc/systemd/system`. This keeps
the demo runnable in place (e.g. `~/workspace/cv-card-demo`) as well as from
`/opt/cv-card-demo` — no hard-coded paths or user.

## Backend Service

- run from the repo root (`@ROOT@`, resolved by `run_backend.sh` itself)
- activate the virtual environment
- export `LD_LIBRARY_PATH` for the bundled NVIDIA CUDA libs (so YOLO uses GPU)
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
