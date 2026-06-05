# CV-Card-Demo – Global MVP Checklist

## Phase Overview

| Phase | Status | Goal |
|---|---|---|
| 01 Boot | DONE | Start backend and UI reliably |
| 02 Init Camera | DONE | Open camera and read valid frames |
| 03 Workspace Calibration | DONE | Define workspace and score axis |
| 04 Card Detection | IN_PROGRESS | Detect valid cards with stable confidence scoring |
| 05 Pose and Score Mapping | IN_PROGRESS | Publish normalized score from workspace x-position |
| 06 Tracking Stability | IN_PROGRESS | Hold tracking through short occlusions and candidate ambiguity |
| 07 Recovery | NOT_STARTED | Recover from camera/backend failures |
| 08 Deployment | IN_PROGRESS | systemd autostart and kiosk mode |
| 09 WLED Output | OPTIONAL | Add optional ESP32/WLED LED output |

## MVP Acceptance Criteria

- [ ] Jetson boots into the application environment
- [ ] Backend starts via systemd
- [ ] UI opens automatically in kiosk mode
- [x] Health endpoint is reachable
- [x] State machine keeps running when a state returns `None`
- [x] `BOOT` transitions to `INIT_CAM`
- [x] Camera opens successfully
- [x] OpenCV reads valid frames
- [x] Detector exposes scored candidates for tracking
- [x] Horizontal card position maps to `0.0 ... 1.0`
- [x] Browser UI can render live score updates from `/ws/score`
- [x] Short card occlusion keeps score visible for up to `tracking_max_lost_duration_s`
- [ ] Real camera tracking verified on Jetson with hand interaction
- [ ] Backend restarts after crash
- [x] WLED is optional and does not block the MVP

## Current Focus

```text
TRACKING_STABILITY / REAL_CAMERA_VALIDATION
```

Next recommended step:

```text
Run the live camera flow on Jetson and verify:
1. detected -> tracked_occluded -> detected payload transitions
2. score bar remains visible during hand-over-card motion
3. real card removal transitions to IDLE_NO_CARD after 0.5 s
```

## Recent Progress

| Date | Change | Status |
|---|---|---|
| 2026-06-05 | Replaced frame-count-only tracking hold with `CardTracker` time-based continuity | DONE |
| 2026-06-05 | Detector now exposes candidate list and uses area/aspect/rectangularity scoring | DONE |
| 2026-06-05 | State machine now stays in the current state when `run()` returns `None` | DONE |
| 2026-06-05 | UI score payload extended with `score`, `state`, and `source` | DONE |

## Known Blockers

| Date | Blocker | Impact | Status |
|---|---|---|---|
| 2026-06-05 | No completed real-camera Jetson validation after tracker rewrite | Blocks marking phases 04-06 as DONE | OPEN |

## Next Recommended Step

```text
Use the real booth camera and capture one short occlusion sequence.
If tracking is stable, close Phase 06 and tighten any remaining detector thresholds from measured data.
```
