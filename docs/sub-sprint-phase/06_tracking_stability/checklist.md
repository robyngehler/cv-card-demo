# Phase Checklist – 06 Tracking Stability

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `06_tracking_stability` |
| Phase Name | `Tracking Stability` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-05 |

## Goal

Keep card feedback alive through short detector dropouts, hand occlusion, and multiple-candidate scenes without jumping to unrelated contours.

## Scope

This phase includes:

- [x] Time-based lost-card hold in `TRACKING`
- [x] Velocity-based prediction for short occlusion windows
- [x] Candidate matching by distance to predicted card position
- [x] Source-aware UI payload: `detected`, `tracked_occluded`, `lost`
- [x] State-machine support for `run() -> None` as stay-in-state

## Non-Goals

This phase explicitly does not include:

- [ ] Hand landmark detection
- [ ] Long-horizon object tracking after real removal
- [ ] Multi-card identity management beyond nearest-neighbor matching

## Implementation Checklist

- [x] Add `CardTracker`
- [x] Seed tracker from `last_candidate`
- [x] Publish last predicted position during short occlusion
- [x] Expire track using `tracking_max_lost_duration_s`
- [x] Add narrow regression script for tracker continuity
- [x] Update UI to show live score and source
- [x] Update `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

## Acceptance Criteria

- [x] Short detector dropout stays in `TRACKING`
- [x] UI payload switches `detected -> tracked_occluded -> detected`
- [x] Track expires after configured lost duration
- [x] Tracker prefers the nearest candidate to the predicted position
- [ ] Real hand-over-card sequence verified on Jetson camera

## Manual Test Steps

### Test 1: Narrow tracker regression

Command:

```bash
python scripts/test_tracking_continuity.py
```

Expected result:

```text
tracking continuity checks passed
```

Status:

```text
PASS (2026-06-05)
```

### Test 2: Live hand-occlusion validation

Command:

```bash
python scripts/analyze_hand_interference.py
```

Expected result:

```text
Detector confidence may dip, but backend should keep publishing score for up to 0.5 s.
```

Status:

```text
NOT_RUN in this session (requires live camera interaction)
```

## Notes

The tracker currently uses nearest-neighbor matching and a short predictive hold. If real-camera testing shows stale tracks, tighten `tracking_match_max_distance_px` or `tracking_max_lost_duration_s` before adding heavier logic.