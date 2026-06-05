# Phase Checklist – 02 Init Camera

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `02_init_cam` |
| Phase Name | `Init Camera` |
| Status | `DONE` |
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

- [x] `INIT_CAM` is entered after `BOOT`
- [x] Camera open/read flow works with a valid device
- [x] `IDLE_NO_CARD` is reached when the first frame is valid
- [x] Repeated failures move the state machine into `RECOVERY`
- [x] Manual test steps are documented
- [x] Known camera issues are recorded

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
PASS
RAN:
(venv) cetibar@ubuntu:~/workspace/cv-card-demo$ cd /opt/cv-card-demo
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
bash: cd: /opt/cv-card-demo: No such file or directory
2026-06-05 15:20:09,957 INFO cv-card-demo Starting state machine in BOOT
2026-06-05 15:20:09,958 INFO cv-card-demo STATE_TRANSITION old_state=BOOT new_state=BOOT reason=enter
2026-06-05 15:20:09,958 INFO cv-card-demo Entering BOOT state
2026-06-05 15:20:09,959 INFO cv-card-demo UI service started on http://0.0.0.0:8000
2026-06-05 15:20:09,960 INFO cv-card-demo BOOT complete, transitioning to INIT_CAM
2026-06-05 15:20:09,960 INFO cv-card-demo Exiting BOOT state
2026-06-05 15:20:09,960 INFO cv-card-demo STATE_TRANSITION old_state=BOOT new_state=INIT_CAM reason=complete
2026-06-05 15:20:09,960 INFO cv-card-demo STATE_TRANSITION old_state=INIT_CAM new_state=INIT_CAM reason=enter
2026-06-05 15:20:09,960 INFO cv-card-demo Entering INIT_CAM state
2026-06-05 15:20:09,961 INFO cv-card-demo Checking OpenCV availability
INFO:     Started server process [30295]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
2026-06-05 15:20:10,206 INFO cv-card-demo OpenCV available: version=4.13.0
2026-06-05 15:20:10,207 INFO cv-card-demo Camera initialization attempt 1/3
2026-06-05 15:20:10,208 INFO cv-card-demo Opening camera device 0
2026-06-05 15:20:11,367 INFO cv-card-demo Camera frame received shape=(480, 640, 3) cv2=4.13.0
2026-06-05 15:20:11,368 INFO cv-card-demo Exiting INIT_CAM state
2026-06-05 15:20:11,368 INFO cv-card-demo STATE_TRANSITION old_state=INIT_CAM new_state=IDLE_NO_CARD reason=complete
2026-06-05 15:20:11,368 INFO cv-card-demo STATE_TRANSITION old_state=IDLE_NO_CARD new_state=IDLE_NO_CARD reason=enter
2026-06-05 15:20:11,368 INFO cv-card-demo Entering IDLE_NO_CARD state
2026-06-05 15:20:11,369 INFO cv-card-demo System is idle and waiting for a card
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
RAN:
(venv) cetibar@ubuntu:~/workspace/cv-card-demo$ curl -i http://localhost:8000/api/health
HTTP/1.1 200 OK
content-type: application/json
{"app":"cv-card-demo","version":"0.1.0","state":"IDLE_NO_CARD","substate":"IDLE_WAITING_FOR_CARD","services":{"camera":{"status":"OK","device_index":0,"frame_shape":[480,640,3],"frames_read":1},"cv2":{"status":"OK","version":"4.13.0"}}}
```

---

## Notes

- Local Logitech BRIO camera test succeeded.
- `/api/health` returns `200 OK` with camera and cv2 status.
- The `INIT_CAM` phase is complete and the next sprint target is workspace calibration.
