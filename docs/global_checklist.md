# CV-Card-Demo – Global MVP Checklist

This checklist tracks the complete demo implementation.

The goal is not to create a perfect product.
The goal is to create a small, stable, locally running booth demo.

---

## Status Labels

Use:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
DEFERRED
OPTIONAL
```

---

## Global MVP Goal

A visitor places a business card or similar card on a table.  
A top-down camera detects the card.  
The card's horizontal position controls a live ranking bar in the browser UI.

Optional later: the same score controls a WLED/ESP32 LED strip.

---

## Phase Overview

| Phase | Status | Goal |
|---|---|---|
| 01 Boot | DONE | Start backend and UI reliably |
| 02 Init Camera | IN_PROGRESS | Open camera and read valid frames |
| 03 UI Service | IN_PROGRESS | Show live status and ranking bar |
| 04 Calibration | NOT_STARTED | Define workspace and score axis |
| 05 Card Detection | NOT_STARTED | Detect card with classical OpenCV |
| 06 Pose and Score Mapping | NOT_STARTED | Convert card position to score |
| 07 Tracking Stability | NOT_STARTED | Smooth score and handle card loss |
| 08 Recovery | NOT_STARTED | Recover from camera/backend failures |
| 09 Deployment | IN_PROGRESS | systemd autostart and kiosk mode |
| 10 WLED Output | OPTIONAL | Add optional ESP32/WLED LED output |

---

## MVP Acceptance Criteria

- [ ] Jetson boots into the application environment
- [ ] Backend starts via systemd
- [ ] UI opens automatically in kiosk mode
- [x] Health endpoint is reachable
- [x] State machine starts in `BOOT`
- [x] `BOOT` transitions to `INIT_CAM`
- [ ] Camera opens successfully
- [ ] OpenCV reads valid frames
- [ ] Card can be detected in the workspace
- [ ] Horizontal card position maps to `0.0 ... 1.0`
- [ ] Browser ranking bar updates live
- [ ] Card loss is handled gracefully
- [ ] Backend restarts after crash
- [x] WLED is optional and does not block the MVP

---

## Current Focus

```text
INIT_CAM / IDLE_NO_CARD
```

Current recommended next step:

```text
Stabilize camera idle behavior and continue into card detection in docs/sub-sprint-phase/03_ui_service/
```

---

## Known Global Blockers

| Date | Blocker | Impact | Status |
|---|---|---|---|
| 2026-06-05 | No usable camera device available at `/dev/video0` during local testing | Blocks full INIT_CAM success | FIXED |
| 2026-06-05 | `IDLE_NO_CARD` exited immediately after enter | Prevented idle state persistence | FIXED |
| 2026-06-05 | Uvicorn config argument unsupported in current environment | Prevented BOOT startup initially | FIXED |

---

## Global Decisions

| Date | Decision | Reason |
|---|---|---|
| TBD | Use classical OpenCV first | Simpler, faster, easier to debug for top-down card detection |
| TBD | WLED is optional | LED output must not block the core UI/CV demo |
| TBD | Use systemd for autostart/recovery | Robust and simple on Ubuntu/Jetson |
| TBD | Use simple HTML/CSS/JS | Avoid unnecessary frontend complexity |

---

## Notes

Keep this file updated when a phase changes status.

Do not add detailed task lists here.
Use the phase-specific `checklist.md` files for detailed work tracking.
