# Phase Checklist – 03 Workspace Calibration

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `03_workspace_calibration` |
| Phase Name | `Workspace Calibration` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-05 |

---

## Goal

Define a stable workspace from the camera image and prepare a transform that the card detector can use. Start with simple manual configuration and keep the result visible in health/UI.

---

## Scope

This phase includes:

- [ ] Add a `CALIBRATION` state
- [ ] Load workspace config
- [ ] Validate workspace geometry against the camera frame
- [ ] Support `manual_rect`
- [ ] Support `manual_quad` if needed
- [ ] Store workspace metadata in health status
- [ ] Keep WLED optional and non-blocking

---

## Non-Goals

This phase explicitly does not include:

- [ ] Card detection
- [ ] Pose estimation
- [ ] Score mapping
- [ ] Tracking stability
- [ ] WLED output
- [ ] Deep learning-based detection

---

## Implementation Checklist

- [ ] Add `WorkspaceService`
- [ ] Add calibration state transitions
- [ ] Add workspace config schema
- [ ] Add workspace validation errors
- [ ] Add health status for workspace
- [ ] Document manual test steps
- [ ] Update `errors_and_fixes.md`
- [ ] Update `docs/global_checklist.md`

---

## Acceptance Criteria

This phase is complete when:

- [ ] `CALIBRATION` exists in the state machine
- [ ] workspace config is loaded and validated
- [ ] a workspace frame can be produced from the camera frame
- [ ] workspace status is visible in the health endpoint
- [ ] invalid workspace config fails visibly
- [ ] manual test steps are documented
- [ ] known workspace issues are recorded

---

## Manual Test Steps

### Test 1: Start backend and reach CALIBRATION

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT -> INIT_CAM -> CALIBRATION -> IDLE_NO_CARD
```

Status:

```text
RAN:
(venv) cetibar@ubuntu:~/workspace/cv-card-demo$ source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
2026-06-05 16:19:34,790 INFO cv-card-demo Starting state machine in BOOT
2026-06-05 16:19:34,790 INFO cv-card-demo STATE_TRANSITION old_state=BOOT new_state=BOOT reason=enter
2026-06-05 16:19:34,790 INFO cv-card-demo Entering BOOT state
2026-06-05 16:19:34,797 INFO cv-card-demo UI service started on http://0.0.0.0:8000
2026-06-05 16:19:34,797 INFO cv-card-demo BOOT complete, transitioning to INIT_CAM
2026-06-05 16:19:34,797 INFO cv-card-demo Exiting BOOT state
2026-06-05 16:19:34,797 INFO cv-card-demo STATE_TRANSITION old_state=BOOT new_state=INIT_CAM reason=complete
2026-06-05 16:19:34,797 INFO cv-card-demo STATE_TRANSITION old_state=INIT_CAM new_state=INIT_CAM reason=enter
2026-06-05 16:19:34,797 INFO cv-card-demo Entering INIT_CAM state
2026-06-05 16:19:34,798 INFO cv-card-demo Checking OpenCV availability
INFO:     Started server process [35851]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
2026-06-05 16:19:35,093 INFO cv-card-demo OpenCV available: version=4.13.0
2026-06-05 16:19:35,094 INFO cv-card-demo Camera initialization attempt 1/3
2026-06-05 16:19:35,094 INFO cv-card-demo Opening camera device 0
2026-06-05 16:19:36,200 INFO cv-card-demo Camera frame received shape=(480, 640, 3) cv2=4.13.0
2026-06-05 16:19:36,201 INFO cv-card-demo Exiting INIT_CAM state
2026-06-05 16:19:36,202 INFO cv-card-demo STATE_TRANSITION old_state=INIT_CAM new_state=CALIBRATION reason=complete
2026-06-05 16:19:36,202 INFO cv-card-demo STATE_TRANSITION old_state=CALIBRATION new_state=CALIBRATION reason=enter
2026-06-05 16:19:36,203 INFO cv-card-demo Entering CALIBRATION state
2026-06-05 16:19:36,229 INFO cv-card-demo Workspace ready mode=manual_rect width=480 height=340
2026-06-05 16:19:36,230 INFO cv-card-demo Exiting CALIBRATION state
2026-06-05 16:19:36,230 INFO cv-card-demo STATE_TRANSITION old_state=CALIBRATION new_state=IDLE_NO_CARD reason=complete
2026-06-05 16:19:36,230 INFO cv-card-demo STATE_TRANSITION old_state=IDLE_NO_CARD new_state=IDLE_NO_CARD reason=enter
2026-06-05 16:19:36,230 INFO cv-card-demo Entering IDLE_NO_CARD state
2026-06-05 16:19:36,230 INFO cv-card-demo System is idle and waiting for a card
```

---

### Test 2: Verify workspace in health

Command:

```bash
curl http://localhost:8000/api/health
```

Expected result:

```text
workspace status is present
workspace mode is present
```

Status:

```text
RAN:
(venv) cetibar@ubuntu:~/workspace/cv-card-demo$ curl http://localhost:8000/api/health
{"app":"cv-card-demo","version":"0.1.0","state":"IDLE_NO_CARD","substate":"IDLE_WAITING_FOR_CARD","uptime_s":112.71,"services":{"ui":{"status":"OK"},"camera":{"status":"OK","device_index":0,"frame_shape":[480,640,3],"frames_read":222},"workspace":{"status":"OK","mode":"manual_rect","width":480,"height":340,"score_axis":"x","invert_score_axis":false,"last_error":null,"rect_px":{"x":80,"y":60,"width":480,"height":340}},"detector":{"status":"OK","visible"
```

---

### Test 3: Invalid workspace config

Expected result:

```text
CALIBRATION fails visibly
state transitions to ERROR_SAFE
health shows workspace.status=ERROR
```

Status:

```text
NOT_RUN
```

---

## Notes

- Start with `manual_rect` before trying perspective transforms.
- Keep calibration simple enough to debug on the booth hardware.
