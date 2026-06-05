# Phase Checklist – 02 Init Camera

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `02_init_cam` |
| Phase Name | `Init Camera` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-05 |

---

## Goal

Open the configured camera and read the first valid frame. Ensure camera initialization is handled in the dedicated `INIT_CAM` state, separate from `BOOT`.

---

## Scope

This phase includes:

- [ ] Create `InitCamState`
- [ ] Probe `cv2` import in `INIT_CAM`
- [ ] Open the camera using a configured device index
- [ ] Read a first valid frame
- [ ] Validate frame shape and capture success
- [ ] Transition to `IDLE_NO_CARD` on success
- [ ] Retry camera open with bounded attempts
- [ ] Move to `RECOVERY` on repeated failure
- [ ] Keep WLED optional and non-blocking

---

## Non-Goals

This phase explicitly does not include:

- [ ] Detecting business cards
- [ ] Mapping score values
- [ ] UI rendering beyond camera status
- [ ] WLED output
- [ ] Deep learning-based detection

---

## Implementation Checklist

- [x] Add `InitCamState`
- [x] Add `CameraService` with `cv2` probe and frame read
- [x] Add retry loop for camera open/read
- [x] Add recovery/error handling for camera failure
- [x] Update health status during `INIT_CAM`
- [x] Document manual test steps
- [x] Update `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

---

## Acceptance Criteria

This phase is complete when:

- [ ] `INIT_CAM` is entered after `BOOT`
- [ ] Camera open/read flow works with a valid device
- [ ] `IDLE_NO_CARD` is reached when the first frame is valid
- [ ] Repeated failures move the state machine into `RECOVERY`
- [ ] Manual test steps are documented
- [ ] Known camera issues are recorded

---

## Manual Test Steps

### Test 1: Start backend and observe `INIT_CAM`

Command:

```bash
cd /opt/cv-card-demo
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT completes
INIT_CAM starts
Camera device is probed
Frame read succeeds
IDLE_NO_CARD is reached and remains active
```

Status:

```text
IN_PROGRESS
```

---

## Notes

- Local Logitech BRIO camera test succeeded
- `IDLE_NO_CARD` now remains active instead of exiting immediately

---

### Test 2: Verify health during `INIT_CAM`

Command:

```bash
curl http://localhost:8000/api/health
```

Expected result:

```text
JSON response with `state`: `INIT_CAM` or later
camera status present
cv2 status present
```

Status:

```text
NOT_RUN
```

---

## Notes

- Current test machine did not have an open `/dev/video0` device.
- The `BOOT` phase is complete; `INIT_CAM` is currently handling camera availability and retry logic.
