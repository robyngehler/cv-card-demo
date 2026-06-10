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

## Unit Binding (why stop/disable work)

The two services are bound to `cv-card-demo.target` so the target controls them
as a unit:

- target `Wants=` both services → `start cv-card-demo.target` starts them.
- each service `PartOf=cv-card-demo.target` → `stop`/`restart cv-card-demo.target`
  propagates to them (PartOf covers stop/restart only, never start).
- each service `[Install] WantedBy=cv-card-demo.target` (NOT multi-user/graphical)
  and only the **target** is `WantedBy=multi-user.target`.

Consequence: `disable cv-card-demo.target` removes the single boot symlink and the
whole stack stops autostarting. Do **not** add `WantedBy=multi-user.target` or
`WantedBy=graphical.target` back to the service units — that reintroduces the bug
where the services autostart and keep running independently of the target (a stop
or disable of the target then has no effect).

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

## Operating the demo

### Install / update the services (renders templates for this checkout)

```bash
./scripts/install_services.sh                 # auto-detect path/user/display
CVD_DISPLAY=:0 ./scripts/install_services.sh   # override kiosk display if needed
```

`install_services.sh` enables the target, so the stack also starts on boot.
Re-run it whenever you move the repo or change the run user.

### Start / stop / restart

```bash
sudo systemctl start   cv-card-demo.target            # start backend + kiosk
sudo systemctl stop    cv-card-demo.target            # stop both
sudo systemctl restart cv-card-demo-backend.service   # restart only the backend
sudo systemctl restart cv-card-demo-kiosk.service     # restart only the kiosk
```

### Status & logs

```bash
systemctl status cv-card-demo-backend.service
journalctl -u cv-card-demo-backend.service -f         # follow backend log live
journalctl -u cv-card-demo-kiosk.service -f
journalctl -u cv-card-demo-backend.service -n 100 --no-pager   # last 100 lines
```

Application-level logs also go to `logs/app.log` in the repo (see config
`logging.file`). On a healthy backend start the log shows:
`YOLO detector ready model=... device=cuda:0` (no "Detector fallback active").

### Enable / disable autostart on boot

```bash
sudo systemctl enable  cv-card-demo.target
sudo systemctl disable cv-card-demo.target
```

### Recover after repeated crashes

`Restart=always` + `StartLimitBurst` means systemd stops retrying after too many
rapid failures ("Start request repeated too quickly"). After fixing the cause,
clear the failed state and start again:

```bash
sudo systemctl reset-failed cv-card-demo-backend.service
sudo systemctl restart cv-card-demo-backend.service
```

### Run in the foreground (no systemd) for development

```bash
./scripts/preflight.sh        # venv / config / CUDA / camera sanity checks
./scripts/run_backend.sh      # Ctrl-C to stop; logs to the terminal
```

The launcher resolves the repo root from its own path, activates the venv,
exports `LD_LIBRARY_PATH` for the bundled CUDA libs, and execs the backend — so
it behaves identically whether run by hand or by systemd.

### Common pitfall

`LD_LIBRARY_PATH: unbound variable` at start means something sourced under
`set -u` references an unset `LD_LIBRARY_PATH` (e.g. a hand-edited
`venv/bin/activate`). The launcher binds it before sourcing activate; do **not**
re-add CUDA path exports to `venv/bin/activate` — `run_backend.sh` owns that.

## Deployment Principle

The deployment path should be boring and reproducible. Boring deployment is good
deployment.
