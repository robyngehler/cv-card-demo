# Errors and Fixes – 09 Frontend Interaction Console

## Status

```text
IN_PROGRESS
```

## 2026-06-08 - Camera Properties Differ Across Drivers

### Context

- service: `camera_control_service`
- endpoints: `/api/camera/settings`, `/api/camera/capabilities`, `/api/camera/restart`

### Observed Behavior

Different OpenCV backends/drivers expose different property support and auto-mode semantics.

### Expected Behavior

Frontend must not assume every property is writable or supported.

### Suspected Cause

V4L2 backend and camera firmware expose a heterogeneous subset of controls.

### Fix Applied

Added capability-aware responses and per-property apply reporting:

- unsupported fields return `supported: false`
- writes return `applied` and `rejected` maps
- frontend disables unsupported controls

### Verification

Command:

```text
get_errors on camera_control_service.py and ui_service.py
```

Expected/observed result:

```text
No static analysis errors.
```

### Status

```text
FIXED
```

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| 2026-06-08 | Target hardware validation pending for real camera controls and full visitor flow | OPEN | Desktop/static checks done; booth run still required |
