# Phase 09 - Frontend Interaction Console Rework

Status: IN_PROGRESS

## Goal

Stabilize the operator UI so RUN and CONFIGURE flows remain responsive and consistent under live camera conditions.

## Scope

- Live frame rendering robustness
- UI snapshot/event update reliability
- Status/diagnostics visual feedback
- Coordinate consistency in tracking overlay
- 1080x720 live processing profile migration

## Non-goals

- Add new ML models
- Add cloud or database features
- Redesign questionnaire logic end-to-end

## Tasks

- [x] Fix card bounding-box overlay coordinates in tracking debug frame
- [x] Add tracking score/rating fields to UI snapshot payload
- [x] Harden SSE stream loop against snapshot-build failures
- [x] Add periodic snapshot polling fallback in frontend
- [x] Stabilize live-view refresh path for CONFIGURE mode
- [x] Improve connection and diagnostics status colors
- [x] Switch live processing to 1080x720 and scale workspace rectangles
- [x] Add score WebSocket live updates to RUN view
- [x] Make CONFIGURE preview fall back to cached live frames
- [x] Reduce snapshot write cost by downscaling saved frames and removing extra debug overlay writes
- [x] Validate runtime behavior on target camera with manual pass
- [x] Add configure-view support for auto toggles and zoom camera control
- [x] Harden camera apply flow with backend-aware auto/manual handling and readback checks
- [x] Harden classical detector geometry/confidence filters against empty-scene false positives
- [x] Expose requested-vs-active detector backend and fallback reason in runtime status

## Acceptance Criteria

- [x] RUN and CONFIGURE both show live feed consistently
- [x] Score/rating and phase/source/confidence update continuously
- [x] Bounding box aligns with card in preview/debug overlays
- [ ] Snapshot transition to SNAPSHOT state is observable during countdown completion

## Manual Test Steps

1. Start backend and open UI.
2. Switch between RUN and CONFIGURE repeatedly.
3. Verify live image appears in both views.
4. Move card and verify score bar/value plus phase/source/confidence updates.
5. Hold card steady for countdown and verify snapshot trigger behavior.
6. Confirm diagnostics drawer and connection pill color states.
7. Verify camera settings readback matches the terminal-side camera values.
8. In an empty workspace (no card/no hand), verify no stable card candidate is accepted.
9. Place a real business card and verify candidate detection still reaches TRACKING.

## Current Status

IN_PROGRESS
