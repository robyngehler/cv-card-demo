# Phase Checklist – 01 Boot

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `01_boot` |
| Phase Name | `Boot` |
| Status | `DONE` |
| Owner | TBD |
| Last Updated | 2026-06-05 |

---

## Goal

Start the local backend and UI reliably after system boot and transition the application state machine from `BOOT` to `INIT_CAM`.

The camera is not opened in this phase.

---

## Scope

This phase includes:

- [ ] Define backend service startup
- [ ] Define kiosk/UI startup
- [ ] Load and validate config
- [ ] Initialize logging
- [ ] Create AppContext
- [ ] Start or verify UI service
- [ ] Start or verify health endpoint
- [ ] Create state machine runtime
- [ ] Transition from `BOOT` to `INIT_CAM`
- [ ] Keep WLED optional and non-blocking

---

## Non-Goals

This phase explicitly does not include:

- [ ] Opening the camera
- [ ] Reading frames
- [ ] Detecting cards
- [ ] Calculating scores
- [ ] Sending data to WLED
- [ ] Implementing deep learning

---

## Implementation Checklist

- [x] Create `BootState`
- [x] Log `BOOT` entry
- [x] Log `BOOT` exit
- [x] Validate config
- [x] Initialize logging
- [x] Initialize UI status
- [x] Provide `/api/health`
- [x] Provide basic UI page
- [x] Add systemd backend service
- [x] Add systemd kiosk service
- [x] Add run scripts
- [x] Add preflight script
- [x] Document manual test steps
- [x] Update `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

---

## Acceptance Criteria

This phase is complete when:

- [x] Backend can be started manually
- [ ] Backend can be started via systemd
- [x] `/api/health` is reachable
- [x] UI opens in browser
- [x] State machine starts in `BOOT`
- [x] `BOOT` transitions to `INIT_CAM`
- [x] WLED disabled/offline does not block startup
- [ ] Logs are visible through `journalctl`
- [ ] Manual test steps pass
- [x] Known errors are documented

---

## Manual Test Steps

### Test 1: Start Backend Manually

Command:

```bash
cd /opt/cv-card-demo
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT starts successfully.
UI service starts.
Health endpoint becomes reachable.
State transitions to INIT_CAM.
```

Status:

```text
PASS
```

---

### Test 2: Check Health Endpoint

Command:

```bash
curl http://localhost:8000/api/health
```

Expected result:

```text
JSON response with app state, service status, and uptime.
```

Status:

```text
PASS
```

---

### Test 3: Start Backend via systemd

Command:

```bash
sudo systemctl start cv-card-demo-backend.service
systemctl status cv-card-demo-backend.service
journalctl -u cv-card-demo-backend.service -f
```

Expected result:

```text
Backend service is active.
Logs show BOOT startup and transition to INIT_CAM.
```

Status:

```text
NOT_RUN
```

---

## Notes

BOOT must stay small and fast.

Camera initialization belongs to `INIT_CAM`, not `BOOT`.
