# Phase Checklist – 07 Tracking Advances

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `07_tracking_advances` |
| Phase Name | `Tracking Advances` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-07 |

## Goal

Keep the visible score stable while a confirmed business card is moved by hand, even when the card contour becomes unreliable.

## Scope

This phase includes:

- [x] Dual `workspace.card` and `workspace.hand` config sections
- [x] Coordinate transform utilities between hand/card/full-frame space
- [x] MediaPipe hand tracker service hook with lazy optional backend loading
- [x] Weighted hand proxy estimator and validity checks
- [x] Card detector abstraction with classical fallback and YOLO interface
- [x] Explicit business-card-only gate for `CANDIDATE_DETECTED`
- [x] Fusion tracker with merge, validation, ambiguous reacquire, and lost hold states
- [x] Exhaustive pending/ambiguous/lost-hold fusion states including `CARD_TO_HAND_PENDING` and lost-hold anchor handling
- [x] Extended WebSocket payload with `fusion_state`, question context, and `candidate_id`
- [x] Debug-frame overlay route for workspaces, card bbox, hand landmarks, proxy, and source

## Non-Goals

This phase explicitly does not include:

- [ ] Physical markers or fixtures
- [ ] Replacing business-card detection with hand-only tracking
- [ ] Hard dependency on YOLO during the MVP
- [ ] Jetson runtime validation in the current Windows session

## Implementation Checklist

- [x] Add `workspace.card` and `workspace.hand` config sections
- [x] Implement coordinate transform utilities
- [x] Add hand workspace debug overlay path
- [x] Implement MediaPipe hand tracker service
- [x] Implement hand proxy estimator
- [x] Add hand proxy validity checks
- [x] Add card detector abstraction and service contract
- [x] Add YOLO card detector interface/stub
- [x] Preserve contour detector as fallback
- [x] Move YOLO detector logic into `app/cv/`
- [x] Move hand proxy and measurement structures into `app/cv/`
- [x] Split fusion engine from fusion service wrapper
- [x] Implement fusion state machine and payload model
- [x] Implement card-to-hand merge
- [x] Implement card-to-hand pending hold to avoid one-frame score drops
- [x] Implement hand-to-card validation without user-visible score drift
- [x] Add score smoothing and lost-hold anchor handling
- [x] Remove artificial card prediction from `TRACKING`
- [x] Extend WebSocket score payload and UI state display
- [x] Add debug frame route for fusion source inspection
- [ ] Test hand-covered-card live scoring on the target environment
- [x] Document errors in `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

## Acceptance Criteria

- [x] Hand workspace maps proxy coordinates back into card score space
- [x] Score follows card when only the card is visible
- [x] Score follows hand proxy after a confirmed card anchor exists
- [x] Score does not jump when hand takes over from card tracking
- [x] Score does not disappear for one frame during card-only -> hand-only takeover
- [x] Score is held stable during ambiguous hand -> card reacquisition
- [x] Lost-hold reacquisition re-aligns against the canonical displayed score instead of accumulating old offsets
- [x] UI payload exposes `fusion_state`, `source`, `question_id`, and `candidate_id`
- [ ] Real camera sequence verified on Jetson with natural hand interaction
- [x] Manual test limits for this session are documented
- [x] `errors_and_fixes.md` is updated
- [x] `docs/global_checklist.md` is updated

## Manual Test Steps

### Test 1: Static validation of tracking slice

Command:

```bash
get_errors on tracking, fusion, hand tracker, detector, UI, and state-machine files
```

Expected result:

```text
No static analysis errors in the modified tracking/runtime slice.
```

Status:

```text
PASS (2026-06-06)
```

### Test 2: Target-environment fusion validation

Command:

```bash
python app/main.py --config config/config.yaml
```

Expected result:

```text
Business-card detection enters CANDIDATE_DETECTED, score transitions card -> hand -> card without visible jumps, and the debug frame shows both workspaces.
```

Status:

```text
NOT_RUN in this session (Windows dev environment; Jetson/live camera validation pending)
```

## Notes

The old tracking sprint allowed a soft hand -> card blend. The new guardrails supersede that behavior: the implementation now freezes the displayed score during hand -> card validation and treats disagreements as ambiguity rather than a correction target.
The tracking state also no longer manufactures predicted card poses; continuity now comes from fusion state and lost-hold anchor handling only.