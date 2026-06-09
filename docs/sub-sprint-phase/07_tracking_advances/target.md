# Sprint Target – 07 Tracking Advances

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `07_tracking_advances` |
| Phase Name | `Tracking Advances` |
| Status | `IN_PROGRESS` |
| Last Updated | 2026-06-07 |

## Objective

Implement a robust interaction-tracking stack that keeps live score updates stable while a visitor moves a business card naturally by hand.

## Guardrail Alignment

- Hand occlusion is treated as expected interaction, not as a short exceptional failure.
- `CANDIDATE_DETECTED` must remain business-card-only. Hand tracking may extend an existing business-card track, but it must never open a session or replace detection.
- The new guardrails override the older sprint wording for hand -> card return: the displayed score must not drift toward a conflicting raw card pose after release.
- YOLO is implemented as an interface/stub path only. The classical contour detector remains the active fallback to keep the MVP runnable and debuggable.

## Target Scope

- Dual card/hand workspaces with coordinate translation back into card score space.
- MediaPipe hand tracker hook plus weighted hand proxy estimation and validity checks.
- Card-detector abstraction that preserves classical contour detection and exposes a future YOLO path.
- Card/hand fusion tracker with explicit `CARD_TO_HAND_MERGE`, `HAND_PROXY_ACTIVE`, `HAND_TO_CARD_VALIDATE`, `CARD_REACQUIRED`, and ambiguous/lost hold handling.
- UI payload and debug-frame path that expose source, fusion state, question phase, and current candidate/session context.

## Current Implementation Status

| Target Item | Status | Notes |
|---|---|---|
| Dual workspace config and transforms | DONE | `workspace.card` and `workspace.hand` are configured and translated through `WorkspaceService`. |
| MediaPipe hand tracker service | DONE | Optional runtime backend with lazy import and validity checks; Windows dev env currently runs in degraded mode when MediaPipe is absent. |
| Hand proxy estimator | DONE | Weighted index/middle proxy plus fallback strategies are implemented. |
| Card detector interface + YOLO stub | DONE | `CardDetectorService` selects classical fallback and exposes YOLO adapter hook. |
| Business-card candidate gate | DONE | Detector and state flow now explicitly keep `CANDIDATE_DETECTED` detector-driven and business-card-only. |
| Fusion tracker | DONE | Exhaustive pending/merge/ambiguous/lost-hold states, anchor-based recovery, and no-drift hand -> card validation are implemented. |
| Tracking loop cleanup | DONE | `TRACKING` uses only real card and hand measurements; artificial predicted card poses were removed. |
| UI debug payload and debug frame route | DONE | WebSocket payload now carries fusion/question context and `/api/debug-frame` serves the tracking overlay. |
| Target-environment runtime validation | NOT_DONE | Windows dev environment only received static validation in this session. |

## Explicit Non-Goals

- Physical markers, rails, holders, or fixtures.
- Hand-only tracking as a substitute for card detection.
- Forcing YOLO into the MVP runtime before classical fallback and the integration contract are stable.
- User-visible score correction after hand release when reacquired card pose disagrees with the last confirmed user score.