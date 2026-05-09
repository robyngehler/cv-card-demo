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

- Confirm the final booth-camera manual pass on the target setup.
- Verify countdown/snapshot transitions in a live run with an actual card.
- Keep snapshot storage lightweight and only retain what helps debugging.

## Acceptance Criteria (MVP)

- Live camera image updates in RUN and CONFIGURE modes.
- Bounding box and landmarks align with card/hand positions in live view.
- Score bar and value update continuously while tracking is visible.
- Questionnaire phase transitions are reflected in UI in near real time.

## Known Blockers

- None confirmed after latest patch pass; requires one last manual booth-style countdown/snapshot check.

## Next Recommended Step

- Run end-to-end manual test in booth setup and tune thresholds if ambient lighting causes unstable candidates.
