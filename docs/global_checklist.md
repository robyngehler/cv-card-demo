# Global MVP Checklist

Status: IN_PROGRESS

## Phases

- [x] 01_boot - DONE
- [x] 02_init_cam - DONE
- [x] 03_workspace_calibration - DONE
- [x] 04_card_detection - DONE
- [x] 05_tracking_ui_integration - DONE
- [ ] 09_frontend_interaction_console_rework - IN_PROGRESS

## Current Focus

- Validate detector behavior after anti-false-positive hardening (empty scene vs real business card).
- Verify YOLO/classical runtime selection visibility in diagnostics and logs.
- Re-run camera control manual pass for exposure/focus/zoom/white-balance apply-readback.

## Acceptance Criteria (MVP)

- Live camera image updates in RUN and CONFIGURE modes.
- Bounding box and landmarks align with card/hand positions in live view.
- Score bar and value update continuously while tracking is visible.
- Questionnaire phase transitions are reflected in UI in near real time.

## Known Blockers

- YOLO is currently configured without model_path, so runtime falls back to classical detector.

## Next Recommended Step

- Run end-to-end booth test and tune detector area/aspect confidence only if real-card recall is too strict.
