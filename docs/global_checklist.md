# Global MVP Checklist

Status: IN_PROGRESS

## Phases

- [x] 01_boot - DONE
- [x] 02_init_cam - DONE
- [x] 03_workspace_calibration - DONE
- [x] 04_card_detection - DONE
- [x] 05_tracking_ui_integration - DONE
- [~] 05_wled_output - IN_PROGRESS (software complete; pending ESP/WLED hardware test)
- [ ] 09_frontend_interaction_console_rework - IN_PROGRESS
- [~] 10_runtime_reliability_perf - IN_PROGRESS (systemd/perf/recovery code complete; pending live restart)

## Current Focus

- Reinstall systemd units once (`./scripts/install_services.sh`) to clear stale
  symlinks so `stop`/`disable cv-card-demo.target` control the whole stack.
- Read `PERF TRACKING ...` lines (journalctl) to localize the periodic latency
  spike to a stage now that timing is always on.
- Wire and bench WLED against real ESP/WLED hardware on the Jetson WLAN.

## Acceptance Criteria (MVP)

- Live camera image updates in RUN and CONFIGURE modes.
- Bounding box and landmarks align with card/hand positions in live view.
- Score bar and value update continuously while tracking is visible.
- Questionnaire phase transitions are reflected in UI in near real time.

## Known Blockers

- WLED phase needs ESP32/WLED hardware reachable on the Jetson WLAN for the live test.

## Resolved

- YOLO now runs on GPU (`detector.backend.device=cuda:0`, status READY) with
  `model_path: ./models/yolov8n.pt`; the classical fallback is no longer engaged.
- MediaPipe was missing from the venv (hand guard silently off) — now installed
  and READY (CPU/XNNPACK; no GPU delegate on aarch64).

## Next Recommended Step

- Restart the backend (`sudo systemctl restart cv-card-demo-backend.service`) to
  load the new code, then watch `journalctl -u cv-card-demo-backend.service -f`
  for `YOLO detector ready ... device=cuda:0`, `hand_tracker READY`, and `PERF`
  lines to confirm GPU + localize the latency spike.
