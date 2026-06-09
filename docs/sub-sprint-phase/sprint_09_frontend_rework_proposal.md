# Sprint 09 Rework Proposal – Frontend Interaction Console Stabilization

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `09_frontend_interaction_console_rework` |
| Phase Name | `Frontend Interaction Console Stabilization` |
| Status | `PROPOSED` |
| Owner | TBD |
| Last Updated | 2026-06-08 |

## Objective

Rework the current frontend implementation into a stable, clean, exhibition-ready interaction console with a reliable live camera view, a questionnaire-first user experience, and a dedicated camera configuration mode that does not fight the tracking loop.

The current implementation created the intended rough building blocks, but the system does not yet provide a usable operator or visitor experience. The main problems are not only visual. They are contract and runtime-flow problems: the frontend receives inconsistent state information, the debug/live image is polled as a still JPEG, camera controls appear to call endpoints whose service backing is not guaranteed, and configuration currently happens while tracking/questionnaire processing may still be active in the background.

## Current Situation Summary

### Implemented So Far

- A tab shell exists with three tabs:
  - `Questionnaire`
  - `Debug`
  - `Control`
- The frontend has been modularized into:
  - `app.js`
  - `js/api.js`
  - `js/state_store.js`
  - `js/tabs.js`
  - `js/questionnaire_view.js`
  - `js/debug_view.js`
  - `js/control_view.js`
- The backend exposes:
  - `/api/health`
  - `/api/state`
  - `/api/debug-frame`
  - `/api/version`
  - `/api/camera/settings`
  - `/api/camera/capabilities`
  - `/api/camera/restart`
  - `/ws/score`
  - `/ws/status`

### Main Problems

1. The questionnaire tab flickers and shows misleading states.
2. Countdown and snapshot states are not visually reliable.
3. The debug/live view is effectively frozen or too slow for meaningful camera adjustment.
4. The control tab exposes too many sliders without a trustworthy live preview or backend confirmation.
5. Most camera settings fail, likely because `camera_control` is missing, incomplete, or not synchronized with the active camera backend.
6. Tab separation is conceptually wrong for the MVP visitor flow: users need to see the live interaction and the question at the same time.
7. The current visual design is too noisy and not aligned with the desired CETI / Robotics Institute Germany inspired clean technical identity.

## Important Architectural Finding

The agent did not completely hallucinate the new modular frontend. The new root `app.js` intentionally imports modules from `./js/...`, and `index.html` loads the root `app.js` as a module:

```html
<script type="module" src="app.js"></script>
```

Expected repo layout:

```text
app/web/index.html
app/web/styles.css
app/web/app.js
app/web/js/api.js
app/web/js/state_store.js
app/web/js/tabs.js
app/web/js/questionnaire_view.js
app/web/js/debug_view.js
app/web/js/control_view.js
```

However, if there is now also an additional `app/web/js/app.js`, that file is almost certainly dead or accidental unless another HTML file imports it explicitly. The agent must remove or ignore duplicate unused entrypoints. The only frontend entrypoint should be:

```text
app/web/app.js
```

The `js/` folder should contain feature modules only, not a second application bootstrap.

## Proposed UX Direction

### Replace Three Equal Tabs With Two Modes

The current three-tab split should be changed.

#### Mode 1: `Run`

This is the primary booth/visitor mode.

Layout:

```text
+----------------------------------------------------------+
| Live camera view with overlays                           |
| - full frame                                             |
| - card workspace                                         |
| - hand workspace                                         |
| - card candidate bbox                                    |
| - hand landmarks / proxy                                 |
| - fusion source indicator                                |
|                                                          |
| Countdown overlay appears here, large and elegant         |
+----------------------------------------------------------+
| Question panel                                           |
| - current question                                       |
| - score bar                                              |
| - min/max labels                                         |
| - visitor guidance message                               |
| - compact phase/fusion/source pills                      |
+----------------------------------------------------------+
```

The live view must take about the upper `2/3` of the screen. The question/score area takes the lower `1/3`. This removes the current conceptual problem where the questionnaire and live view are split into different tabs, which forces the user/operator to choose between seeing the actual interaction and seeing the question.

#### Mode 2: `Configure Camera`

This is an operator-only mode.

Layout:

```text
+----------------------+-----------------------------------+
| Camera settings      | Live camera preview               |
| - exposure           |                                   |
| - focus              | large preview, about 2/3 width    |
| - sharpness          | with workspace overlays optional  |
| - brightness         |                                   |
| - contrast           |                                   |
| - auto toggles       |                                   |
| - apply/restart      |                                   |
+----------------------+-----------------------------------+
```

The camera preview must be visible while changing settings. Sliders should not spam the backend on every `input` event. Either:

- apply on `change` after the slider is released, or
- update the label on `input` but only send values when pressing `Apply`, or
- add a debounced preview mode only if performance is proven acceptable.

For MVP stability, prefer explicit `Apply` plus optional `Apply on release`.

#### Optional Mode 3: `Diagnostics`

A reduced diagnostics panel may remain, but it should not be the primary visitor experience. It should be used for developers/operators only.

## Evaluation Of User Solution Suggestions

### Suggestion: Use SSE For Refresh

Assessment: useful, but not sufficient alone.

The current problem is not simply that polling is bad. The bigger problem is that different data channels are used inconsistently:

- `/ws/score` provides score events.
- `/api/state` is polled once per second.
- `/api/health` is polled every two seconds.
- `/api/debug-frame` is polled as JPEG only while the Debug tab is active.

This creates stale state, flicker, and split-brain UI behavior. A single consolidated event stream is recommended.

Recommended approach:

```text
/api/events  -> Server-Sent Events for low/mid-frequency state updates
/api/video.mjpeg or /api/live-frame -> continuous visual stream
/ws/score may remain temporarily but should not be the only source of truth
```

SSE is better than polling for state, session, phase, health, and camera-control status. It is not the right transport for actual video frames. For video, use MJPEG streaming or controlled image polling with explicit timestamps.

### Suggestion: Add A `CONFIGURE_CAMERA` State

Assessment: strongly recommended.

Camera configuration should not run while the normal card detection, hand tracking, questionnaire, OCR triggers, and snapshot states are active. Camera tuning changes exposure/focus and may temporarily invalidate detection and score stability. Letting the full tracking loop continue in the background during configuration is how one gets haunted UX. Very modern, very cursed.

Add a state such as:

```text
CONFIGURE_CAMERA
```

or, more explicitly:

```text
CAMERA_CONFIG
```

Expected behavior:

- Pause questionnaire progression.
- Do not create or advance sessions.
- Do not run candidate precheck.
- Do not trigger countdown or snapshot.
- Keep camera open if possible.
- Run lightweight frame capture and overlay rendering only.
- Allow camera settings to be applied safely.
- Allow transition back to `IDLE_NO_CARD`.
- Optionally allow transition to `INIT_CAM` or `CALIBRATION` after settings change.

### Suggestion: Merge Tab 1 And Tab 2

Assessment: strongly recommended.

Questionnaire and live view are the same user journey. Splitting them makes the UI technically organized but experientially wrong. The visitor needs to see the visual interaction and the current question at the same time.

The proposed Run layout should merge them.

### Suggestion: CI Inspired By CETI And Robotics Institute Germany

Assessment: recommended as visual direction, but implement locally without external dependencies.

Design principles:

- dark or off-white technical background
- clean grid layout
- strong typography
- thin outlines, restrained gradients
- accent colors inspired by technical research branding
- avoid overloaded neon gaming dashboard aesthetics
- large live camera area
- minimal but precise state labels

Do not copy external CSS or assets. Use the sites only as direction.

### Suggestion: Backend Scan And API Integration

Assessment: mandatory.

The frontend currently calls camera-control routes. These routes return `NOT_INITIALIZED` when `camera_control` is missing. The agent must verify whether the service exists, is registered in the app context, and can actually apply settings to the currently active camera backend.

## Backend Rework Targets

### 1. Consolidated Frontend State Contract

Add a single UI snapshot model that is the authoritative frontend state.

Endpoint:

```text
GET /api/ui/snapshot
```

SSE endpoint:

```text
GET /api/ui/events
```

Event type:

```json
{
  "type": "ui_snapshot",
  "timestamp": 1710000000.123,
  "app": {
    "state": "TRACKING",
    "substate": null,
    "mode": "RUN"
  },
  "session": {
    "session_id": "...",
    "candidate_id": "cand_email_...",
    "identity_status": "MATCHED_EMAIL",
    "question_index": 1,
    "question_count": 5,
    "current_question_id": "q_02",
    "completed": false
  },
  "questionnaire": {
    "phase": "COUNTDOWN",
    "question_label": "How relevant is this topic for your work?",
    "min_label": "Not relevant",
    "max_label": "Very relevant",
    "score": 0.72,
    "rating": 7.2,
    "visible": true,
    "countdown_remaining_s": 1.8,
    "snapshot_pending": false,
    "message": "Hold position"
  },
  "tracking": {
    "source": "hand_proxy",
    "fusion_state": "HAND_PROXY_ACTIVE",
    "confidence": 0.83,
    "card_visible": false,
    "hand_visible": true,
    "candidates_count": 1
  },
  "camera": {
    "mode": "tracking",
    "opened": true,
    "frame_shape": [2160, 3840, 3],
    "settings_status": "OK",
    "last_error": null
  },
  "services": {
    "detector": "OK",
    "hand_tracker": "OK",
    "snapshot_processing": "OK",
    "ocr": "DEGRADED",
    "vector": "IN_MEMORY_NON_PERSISTENT"
  }
}
```

Rules:

- The frontend must render from this snapshot, not from a mix of partially stale `score`, `state`, and `health` objects.
- `questionnaire.phase` is the only value used for countdown/snapshot UI.
- `app.state` is displayed as technical detail, not as the primary user-facing state.
- Every snapshot must include a `timestamp`.
- The backend should only emit when relevant values change, or at a low fixed heartbeat such as 5 Hz.

### 2. Live Frame Streaming

Current `/api/debug-frame` returns a single JPEG from `runtime["last_debug_frame_jpeg"]`. This is useful for debugging but not enough for a live view if it is only refreshed on one tab or if the backend frame is not updated regularly.

Add one of these:

Preferred:

```text
GET /api/live.mjpeg
```

Fallback:

```text
GET /api/live-frame?mode=run&ts=...
```

Requirements:

- The stream must work in both Run and Configure Camera modes.
- It must include overlays depending on mode:
  - Run: card workspace, hand workspace, bbox, hand landmarks/proxy, fusion source.
  - Configure: optional workspace overlays, focus/exposure status, no questionnaire overlays.
- Frame responses must include a generated timestamp or sequence number.
- The frontend must not reuse old object URLs forever. Revoke old blob URLs to avoid memory leaks.

### 3. Camera Configure State

Add a backend mode/state:

```text
CAMERA_CONFIG
```

Transitions:

```text
IDLE_NO_CARD -> CAMERA_CONFIG
CAMERA_CONFIG -> IDLE_NO_CARD
CAMERA_CONFIG -> INIT_CAM       optional after restart
CAMERA_CONFIG -> CALIBRATION    optional after resolution/workspace changes
```

API:

```text
POST /api/mode/configure-camera
POST /api/mode/run
```

Behavior:

`POST /api/mode/configure-camera`:

- Set runtime mode to camera configuration.
- Stop questionnaire progression.
- Stop countdown/snapshot triggers.
- Keep lightweight frame capture active.
- Publish UI snapshot with `app.mode = "CONFIGURE_CAMERA"`.

`POST /api/mode/run`:

- Leave configuration mode.
- Re-enter `IDLE_NO_CARD` or `INIT_CAM` depending on whether camera restart/reinit is required.
- Refresh settings/capabilities.

### 4. Camera Control Service Contract

The current frontend expects:

```text
GET  /api/camera/settings
POST /api/camera/settings
POST /api/camera/restart
```

The backend must guarantee that `camera_control` is registered or the UI must degrade clearly.

Required service methods:

```python
get_settings() -> dict
get_capabilities() -> dict
apply_settings(payload: dict) -> dict
restart_camera() -> dict
```

Required response shape:

```json
{
  "status": "OK | PARTIAL | ERROR | NOT_SUPPORTED | NOT_INITIALIZED",
  "settings": {
    "exposure": {
      "value": 120,
      "min": 1,
      "max": 10000,
      "step": 1,
      "supported": true,
      "auto_supported": true,
      "auto": false,
      "requires_restart": false
    }
  },
  "applied": {
    "exposure": 120
  },
  "rejected": {
    "focus": "not_supported_by_backend"
  },
  "last_error": null
}
```

Rules:

- Unsupported controls must be hidden or disabled, not rendered as fake usable sliders.
- Backend must report actual camera property values after apply.
- If a property requires restart/reinit, frontend must show it before applying.
- If OpenCV/V4L2 cannot set a property while streaming, the response must say so explicitly.

### 5. State Flicker Fix

Current flicker likely comes from these causes:

- WebSocket score updates and `/api/state` polling update overlapping state fields at different rates.
- `question_phase` may fall back from score payload to session phase and back.
- Technical backend state and questionnaire user phase are treated as equivalent.
- Polling can overwrite newer WebSocket data with stale `/api/state` data.

Fix strategy:

- Replace UI rendering source with unified `ui_snapshot`.
- Keep a frontend `lastTimestamp` and ignore older events.
- Separate technical state from user-facing phase:
  - `app.state`: `TRACKING`, `SNAPSHOT`, `IDLE_NO_CARD`
  - `questionnaire.phase`: `WAIT_FOR_MOVEMENT`, `WAIT_FOR_STABILITY`, `COUNTDOWN`, `SNAPSHOT`, `NEXT_QUESTION`, `COMPLETE`
- Never use `app.state` alone to decide whether countdown is visible.
- Countdown overlay depends only on `questionnaire.phase` and `countdown_remaining_s`.

## Frontend Rework Targets

### 1. New Layout

Replace the current tab shell with:

```text
Header
  - app name
  - connection status
  - mode toggle: Run / Configure

Run View
  - top: live visual panel, 2/3 height
  - bottom: question + score panel, 1/3 height

Configure View
  - left: camera settings, 1/3 width
  - right: live visual panel, 2/3 width

Diagnostics Drawer / Optional Tab
  - technical runtime
  - service status
  - frontend timeline
```

### 2. Run View Details

Run view must show:

- live visual stream
- current question
- score bar
- score value
- min/max labels
- compact state pills:
  - candidate/identity
  - fusion source
  - phase
  - tracking confidence
- countdown overlay over live image:
  - large number
  - animated lock/capture ring
  - `Hold still` / `Capturing` copy

Do not show long technical labels as primary visual elements.

### 3. Configure View Details

Configure view must show:

- large live preview on the right
- settings on the left
- grouped controls:
  - Exposure
  - Focus
  - Image quality
  - White balance/color
  - Camera lifecycle
- disabled unsupported controls
- `Apply`, `Reset`, `Restart Camera`, `Back to Run`
- backend response result with rejected keys and errors
- optional `apply on release` toggle

Do not render a slider if the backend cannot confirm support.

### 4. Diagnostics

Diagnostics may show:

- full UI snapshot JSON summary
- service statuses
- state transitions
- frame age
- dropped/rejected camera settings
- recent frontend events

Diagnostics should not distract from the Run view.

## File-Level Implementation Plan

### Backend Files To Inspect / Modify

Likely files:

```text
app/services/ui_service.py
app/services/health_service.py
app/services/camera_service.py
app/services/camera_control_service.py  # create if missing
app/state_machine.py
app/states/idle.py
app/states/init_cam.py
app/states/calibration.py
app/states/tracking.py
app/states/snapshot.py
app/context.py or equivalent service registry
config/config.yaml
```

Required backend tasks:

- [ ] Verify whether `camera_control` is registered in app context.
- [ ] Add or fix `CameraControlService`.
- [ ] Add `/api/ui/snapshot`.
- [ ] Add `/api/ui/events` using SSE.
- [ ] Add `/api/live.mjpeg` or improve `/api/debug-frame` into a reliable live stream.
- [ ] Add mode switch endpoints for Run and Configure Camera.
- [ ] Add `CAMERA_CONFIG` state or runtime mode.
- [ ] Ensure Configure mode pauses questionnaire/session progression.
- [ ] Ensure Configure mode still produces live frames.
- [ ] Add backend timestamps to all UI state payloads.
- [ ] Ensure all camera setting errors are reported with actionable reasons.

### Frontend Files To Inspect / Modify

Expected final layout:

```text
app/web/index.html
app/web/styles.css
app/web/app.js
app/web/js/api.js
app/web/js/state_store.js
app/web/js/run_view.js
app/web/js/configure_view.js
app/web/js/diagnostics_view.js
app/web/js/live_view.js
```

Recommended cleanup:

- [ ] Replace `questionnaire_view.js` and `debug_view.js` split with `run_view.js` plus shared `live_view.js`.
- [ ] Replace `control_view.js` with `configure_view.js` using a live preview.
- [ ] Keep `state_store.js`, but base it on `ui_snapshot` instead of merging scattered payloads.
- [ ] Remove duplicate or unused `app/web/js/app.js` if present.
- [ ] Keep only root `app/web/app.js` as bootstrap.
- [ ] Add stale-frame detection and visible frame age.
- [ ] Revoke old frame blob URLs if polling remains.
- [ ] Do not poll debug frames only in Debug tab; Run and Configure both need visual preview.

## Documentation Requirements

Create or update:

```text
docs/sub-sprint-phase/09_frontend_interaction_console_rework/target.md
docs/sub-sprint-phase/09_frontend_interaction_console_rework/checklist.md
docs/sub-sprint-phase/09_frontend_interaction_console_rework/errors_and_fixes.md
docs/global_checklist.md
```

Documentation rule:

- Any code change must update the phase docs.
- Any failed backend endpoint or camera setting issue must be logged in `errors_and_fixes.md`.
- If the agent discovers an endpoint was invented without service backing, document it explicitly.

## Acceptance Criteria

### Run View

- [ ] Run view combines live camera and questionnaire in one screen.
- [ ] Live camera updates continuously with visible frame age under 300 ms target on Jetson if feasible.
- [ ] Workspace overlays, card bbox, hand landmarks/proxy, and fusion source can be inspected.
- [ ] Current question is always visible during interaction.
- [ ] Score bar updates without flicker.
- [ ] Countdown appears as a large overlay over the live image.
- [ ] Snapshot phase is visually distinct from countdown.
- [ ] Technical state changes no longer cause user-facing layout flicker.

### Configure Camera

- [ ] Configure mode pauses questionnaire and tracking side effects.
- [ ] Configure mode shows live preview on the right and settings on the left.
- [ ] Unsupported settings are disabled or hidden.
- [ ] Settings are applied only on explicit Apply or slider release, not on every pixel movement.
- [ ] Backend response clearly reports applied and rejected values.
- [ ] Camera restart/reinit path works or reports a clear reason why not.
- [ ] Returning to Run mode re-enters a clean idle state.

### Backend/API

- [ ] `/api/ui/snapshot` returns one complete authoritative state object.
- [ ] `/api/ui/events` streams consistent state updates or documented fallback polling exists.
- [ ] `/api/live.mjpeg` or equivalent live-frame endpoint updates reliably.
- [ ] Camera-control routes are backed by a registered service.
- [ ] Camera-control service reports real capabilities from the active backend.
- [ ] No frontend route calls an endpoint that is unimplemented or fake-successful.

### Design

- [ ] UI is clean, technical, and readable from booth distance.
- [ ] Visual hierarchy prioritizes live camera, question, score, countdown.
- [ ] Diagnostics are available but visually secondary.
- [ ] Styling is inspired by CETI / Robotics Institute Germany direction without copying assets.

## Manual Test Plan

### Test 1: Frontend Entrypoint Sanity

Command:

```bash
find app/web -maxdepth 3 -type f | sort
```

Expected:

```text
Only one app bootstrap exists: app/web/app.js
Feature modules live in app/web/js/
No unused app/web/js/app.js unless explicitly imported
```

### Test 2: Backend Route Sanity

Command:

```bash
curl -s http://localhost:8000/api/ui/snapshot | jq
curl -s http://localhost:8000/api/health | jq
curl -s http://localhost:8000/api/camera/settings | jq
```

Expected:

```text
All endpoints return structured JSON.
Camera settings either work or clearly report NOT_SUPPORTED / NOT_INITIALIZED with reason.
```

### Test 3: Run Mode Live Interaction

Command:

```bash
python -m app.main --config config/config.yaml
```

Expected:

```text
Run view shows live frame, overlays, current question, score bar, countdown overlay, and snapshot phase without flicker.
```

### Test 4: Configure Mode

Steps:

1. Open frontend.
2. Switch to Configure Camera.
3. Confirm live preview continues.
4. Change exposure/focus.
5. Apply settings.
6. Confirm backend reports applied/rejected values.
7. Return to Run.

Expected:

```text
No questionnaire progression occurs during configuration.
Camera preview remains live.
Returning to Run starts from a clean idle/candidate detection path.
```

### Test 5: Stale Frame Detection

Steps:

1. Stop camera or freeze backend frame generation.
2. Observe UI.

Expected:

```text
UI clearly reports stale live frame instead of silently showing a frozen image.
```

## Non-Goals

This rework does not include:

- A full design system implementation.
- Cloud dashboard features.
- User login or admin auth.
- Perfect cross-browser support beyond the kiosk browser target.
- Replacing the CV pipeline itself.
- Solving all camera-driver limitations if the hardware/backend does not support a property.

## Final Implementation Order

1. Remove duplicate frontend entrypoints and confirm file structure.
2. Add unified backend `ui_snapshot` model.
3. Add SSE state stream or stable fallback polling based on timestamps.
4. Add reliable live-frame endpoint.
5. Add `CAMERA_CONFIG` mode/state and mode switch endpoints.
6. Fix/register `CameraControlService`.
7. Rebuild frontend into Run + Configure + optional Diagnostics.
8. Apply clean CI styling.
9. Run manual tests on dev machine.
10. Run live validation on Jetson/camera target.
11. Update phase docs and global checklist.

## Agent Guardrails

- Do not invent frontend endpoints without implementing backend routes.
- Do not render controls that the backend cannot support.
- Do not use `app.state` as the primary questionnaire phase.
- Do not let `/api/state` polling overwrite newer websocket/SSE data.
- Do not run camera configuration while questionnaire countdown/snapshot can trigger.
- Do not keep a frozen frame without visible stale-frame warning.
- Do not create a second `app.js` entrypoint in `app/web/js/`.
- Do not mark this sprint done without Jetson/live-camera validation or a documented reason why it could not be run.
