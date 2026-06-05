# Phase Checklist – 04 Card Detection

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `04_card_detection` |
| Phase Name | `Card Detection` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-05 |

## Goal

Detect a card inside the calibrated workspace with a simple classical OpenCV pipeline and expose enough scored candidates for the tracking phase.

## Scope

This phase includes:

- [x] Classical contour-based detector
- [x] `CardPose` / `CardDetectionResult` structures
- [x] Confidence scoring with area, aspect ratio, and rectangularity
- [x] `x_normalized` output for downstream score publishing
- [x] Detector runtime status for health/debugging

## Non-Goals

This phase explicitly does not include:

- [ ] Deep learning-based detection
- [ ] Multi-camera support
- [ ] Occlusion hold logic in `TRACKING`
- [ ] WLED output

## Implementation Checklist

- [x] Add `ClassicalCardDetector`
- [x] Make preprocessing and scoring configurable
- [x] Expose sorted candidate list for tracker matching
- [x] Add detector debug overlay and analysis scripts
- [x] Keep implementation local and dependency-light
- [x] Update `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

## Acceptance Criteria

- [x] Detector returns `visible=false` when no card is present
- [x] Detector returns `visible=true` with a best candidate for a clear card
- [x] Detector returns `x_normalized` in `0.0 ... 1.0`
- [x] Detector exposes candidate list for tracking continuity
- [x] Detector status is visible in health endpoint
- [ ] Real camera confidence tuning verified on Jetson

## Manual Test Steps

### Test 1: Synthetic detector regression

Command:

```bash
python scripts/test_detector_batch.py
```

Expected result:

```text
Card detected with confidence above min_confidence and a saved debug frame.
```

Status:

```text
PASS (2026-06-05)
confidence=0.907, x_normalized=0.429
```

### Test 2: Detector + tracker preflight

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

## Notes

Tracking continuity and hand-occlusion behavior are documented in Phase 06 to avoid duplicating the same issue across phases.
