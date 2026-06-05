# Errors and Fixes – 01 Boot

This file documents boot-related errors, failures, workarounds, and fixes.

---

## Status

```text
IN_PROGRESS
```

---

## 2026-06-05 – Uvicorn `Config()` argument caused BOOT startup failure

### Context

- state: `BOOT`
- service: `ui_service`
- command: `python -m app.main --config config/config.yaml --initial-state BOOT`

### Observed Behavior

The backend failed to start because Uvicorn rejected an unsupported config argument.

### Expected Behavior

The UI service should start successfully and BOOT should transition to `INIT_CAM`.

### Logs / Evidence

```text
UI service failed to start: Config.__init__() got an unexpected keyword argument 'install_signal_handlers'
```

### Suspected Cause

The installed Uvicorn version does not support `install_signal_handlers` in `uvicorn.Config`.

### Fix Applied

Removed `install_signal_handlers=False` from `uvicorn.Config(...)` in `app/services/ui_service.py`.

### Verification

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected/observed result:

```text
UI service started on http://0.0.0.0:8000
BOOT transitions to INIT_CAM
```

### Status

```text
FIXED
```

---

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| 2026-06-05 | Uvicorn startup config arg failure | FIXED | Fixed in `app/services/ui_service.py` |

---

## Error Entry Template

```markdown
## <YYYY-MM-DD> – <Short Error Title>

### Context

Example:

- state: `BOOT`
- service: `backend`
- command: `sudo systemctl start cv-card-demo-backend.service`

### Observed Behavior

What happened?

### Expected Behavior

What should have happened?

### Logs / Evidence

```text
paste short relevant log excerpt here
```

### Suspected Cause

Short factual explanation.

If not confirmed:

```text
Cause not confirmed yet.
```

### Fix Applied

What was changed?

### Verification

Command:

```bash
# command here
```

Expected/observed result:

```text
result here
```

### Status

Use one:

```text
OPEN
FIXED
WORKAROUND
DEFERRED
CANNOT_REPRODUCE
```
```
