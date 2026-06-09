# Sprint Target Proposal – 09 Frontend Interaction Console

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `09_frontend_interaction_console` |
| Phase Name | `Frontend Interaction Console` |
| Status | `PROPOSED` |
| Owner | TBD |
| Last Updated | 2026-06-08 |

## Objective

Implement the next frontend sprint as a production-ready exhibition UI with three explicit user-facing modes:

1. **Debug View** for developers and booth operators.
2. **Control Tab** for camera and capture tuning.
3. **Questionnaire Tab** for the visitor-facing scoring experience.

The frontend must make the existing backend state, tracking, fusion, questionnaire, and debug data understandable without forcing the operator to read logs like some medieval punishment ritual.

## Current Backend/UI Baseline

The existing backend already exposes:

- `GET /api/health` for app, state, session, tracking, and service status.
- `GET /api/state` for current state, substate, session context, and tracking context.
- `GET /api/debug-frame` for the current JPEG debug overlay.
- `GET /api/version` for app metadata.
- `WS /ws/score` for live score/questionnaire payloads.
- `WS /ws/status` for system status messages.

The current static frontend already renders a single-page questionnaire/debug hybrid using:

- `index.html`
- `styles.css`
- `app.js`

This sprint should evolve that prototype into a tabbed interface instead of replacing the backend architecture.

## Guardrail Alignment

- Do not block the live scoring loop with frontend polling or heavy image refresh logic.
- Keep the questionnaire flow config-driven; question text and scale labels must come from backend payload/config, not hardcoded frontend assumptions.
- Keep `CANDIDATE_DETECTED` business-card anchored. The UI may visualize hand tracking, but must not imply that hand-only tracking starts a session.
- Keep metadata/OCR/vector processing visibly asynchronous. The UI may show status, but must not wait for metadata before moving through questions.
- Keep frontend additions dependency-light. Prefer plain HTML/CSS/JavaScript unless a framework is already part of the repository.
- Operator controls must be explicit, reversible where possible, and must show whether the backend accepted or rejected a setting.
- Debug overlays must make coordinate-space issues visible: full frame, workspace, card workspace, hand workspace, card candidate, rigid hand/proxy, keypoints, source, and fusion state.

## Target Scope

### 1. App Shell and Navigation

Create a clean tabbed layout with three main tabs:

```text
Questionnaire | Debug | Control
```

Suggested files:

```text
app/web/index.html
app/web/styles.css
app/web/app.js
```

Optional split if the agent wants to improve structure without introducing a framework:

```text
app/web/js/api.js
app/web/js/state_store.js
app/web/js/tabs.js
app/web/js/questionnaire_view.js
app/web/js/debug_view.js
app/web/js/control_view.js
app/web/js/countdown_view.js
app/web/css/base.css
app/web/css/questionnaire.css
app/web/css/debug.css
app/web/css/control.css
```

If splitting files, keep `index.html` as the single browser entrypoint.

### 2. Questionnaire Tab

Implement the visitor-facing UI.

Required elements:

- Current question title.
- Optional question description/help text if present in payload/config.
- Live score bar from normalized score `0.0 ... 1.0`.
- Numeric rating display, preferably `0 ... 10` with one decimal if available.
- Min/max labels from backend payload.
- Current phase display:
  - `WAIT_FOR_MOVEMENT`
  - `ACTIVE_SCORING`
  - `WAIT_FOR_STABILITY`
  - `COUNTDOWN`
  - `SNAPSHOT`
  - `NEXT_QUESTION`
  - `COMPLETED`
- Candidate identity message:
  - “Recognizing card...”
  - “Welcome back”
  - “New visitor”
  - fallback/operator-safe message when identity is unknown.
- Smooth score animation that follows live updates without lagging behind actual state.
- A premium countdown experience for snapshot capture.

Countdown design requirements:

- Do not use a plain large `3, 2, 1` block as the only visual.
- Use a compact cinematic countdown pattern:
  - circular progress ring,
  - short pulse animation,
  - text such as `Locking answer`, `Capturing snapshot`, `Hold still`,
  - optional microcopy: `Keeping score fixed while we capture the card`.
- The countdown must be driven by backend `countdown_remaining_s` if available.
- If only phase is available, show an indeterminate “preparing snapshot” animation instead of inventing timing.

### 3. Debug View

Implement a developer/operator debug panel that shows everything required to understand the current phase.

Required sections:

#### Live Visual Panel

Display the current debug image from:

```text
GET /api/debug-frame
```

Refresh at a configurable rate, default:

```text
5 Hz
```

The refresh loop must pause when the Debug tab is not visible to avoid wasting Jetson resources, because apparently GPUs also enjoy breathing.

Required display options:

- Full debug overlay image.
- Toggle overlay layer visibility in the UI if backend supports separate layers later.
- Show timestamp / age of last successfully loaded frame.
- Show fallback state when endpoint returns `204`.

#### Runtime State Panel

Show from `GET /api/state`, `GET /api/health`, and `WS /ws/score`:

- current state
- substate
- session id
- candidate id
- identity status
- question id
- question phase
- visible / not visible
- score
- rating
- source
- fusion state
- detector confidence if present
- card bbox / center / score axis if present
- hand proxy position if present
- hand landmark count / confidence if present
- snapshot state if present
- OCR/vector/persistence status from health if present

#### Debug Timeline

Add a lightweight rolling event list for the latest frontend-observed events:

- WebSocket connected/disconnected.
- State changed.
- Phase changed.
- Fusion state changed.
- Candidate changed.
- Countdown started.
- Snapshot triggered.
- Health degraded/recovered.

This can be frontend-only for now.

### 4. Control Tab

Implement an operator control page for camera and capture settings.

Minimum required controls:

- Exposure
- Focus
- Sharpness
- Brightness
- Contrast
- Saturation
- Gain
- White balance / auto white balance
- Auto exposure toggle
- Auto focus toggle
- Debug frame refresh rate
- Optional camera restart button if backend supports it later.

Backend API requirement:

Add explicit endpoints if they do not exist yet:

```http
GET /api/camera/settings
POST /api/camera/settings
POST /api/camera/restart
GET /api/camera/capabilities
```

Proposed `GET /api/camera/settings` response:

```json
{
  "status": "OK",
  "device_index": 0,
  "backend": "opencv",
  "settings": {
    "exposure": { "value": -6, "min": -13, "max": 0, "step": 1, "auto": false, "supported": true },
    "focus": { "value": 30, "min": 0, "max": 255, "step": 1, "auto": false, "supported": true },
    "sharpness": { "value": 128, "min": 0, "max": 255, "step": 1, "supported": true },
    "brightness": { "value": 128, "min": 0, "max": 255, "step": 1, "supported": true },
    "contrast": { "value": 128, "min": 0, "max": 255, "step": 1, "supported": true },
    "saturation": { "value": 128, "min": 0, "max": 255, "step": 1, "supported": true },
    "gain": { "value": 0, "min": 0, "max": 255, "step": 1, "supported": true },
    "white_balance": { "value": 4500, "min": 2800, "max": 6500, "step": 100, "auto": true, "supported": true }
  },
  "last_error": null
}
```

Proposed `POST /api/camera/settings` request:

```json
{
  "exposure": -6,
  "auto_exposure": false,
  "focus": 30,
  "auto_focus": false,
  "sharpness": 128
}
```

Proposed response:

```json
{
  "status": "OK",
  "applied": {
    "exposure": true,
    "auto_exposure": true,
    "focus": true,
    "auto_focus": true,
    "sharpness": true
  },
  "rejected": {},
  "last_error": null
}
```

If OpenCV/camera backend does not support a property, return `supported: false` and keep the frontend control disabled.

### 5. API Client and State Store

Implement a small frontend state store in plain JavaScript.

Required behavior:

- One WebSocket connection to `/ws/score`.
- Reconnect with exponential backoff up to a reasonable cap.
- Poll `/api/state` at low frequency, default `1 Hz`.
- Poll `/api/health` at low frequency, default `0.5 Hz`.
- Poll `/api/debug-frame` only while Debug tab is active.
- All incoming data should merge into one frontend state object.
- Views render from that state object; avoid each component independently fetching random endpoints like a flock of caffeinated pigeons.

Suggested frontend state shape:

```js
{
  connection: {
    scoreWs: "CONNECTED",
    lastScoreAt: "...",
    backendReachable: true
  },
  app: {
    state: "TRACKING",
    substate: null,
    version: "0.1.0"
  },
  session: {
    session_id: "...",
    candidate_id: "...",
    identity_status: "...",
    current_question_id: "...",
    phase: "COUNTDOWN",
    completed: false
  },
  score: {
    visible: true,
    score: 0.72,
    rating: 7.2,
    source: "hand_proxy",
    fusion_state: "HAND_PROXY_ACTIVE",
    countdown_remaining_s: 1.8
  },
  health: {
    services: {}
  },
  camera: {
    settings: {},
    capabilities: {},
    last_error: null
  }
}
```

### 6. Backend Service Additions

Add or extend services only where required.

Suggested backend additions:

```text
app/services/camera_control_service.py
```

Responsibilities:

- read current camera properties
- expose capabilities where possible
- apply supported settings
- report rejected/unsupported values
- keep camera backend specifics away from `UIService`

Extend `UIService` routes:

```python
@self.app.get("/api/camera/settings")
@self.app.post("/api/camera/settings")
@self.app.get("/api/camera/capabilities")
@self.app.post("/api/camera/restart")
```

Do not place camera-specific logic directly inside route handlers beyond request parsing and service delegation.

### 7. Visual Design Direction

Design style:

- professional exhibition booth
- customer friendly
- dark technical premium UI
- high contrast for kiosk visibility
- large readable typography
- no visual clutter on Questionnaire tab
- dense information allowed only on Debug tab
- Control tab should look like an operator console, not a random settings dump.

Suggested UI behavior:

- Questionnaire tab is default.
- Debug tab is operator-focused and can be opened manually.
- Control tab requires clear “Apply” feedback.
- Degraded backend/service states should be visible but not panic-inducing.
- The UI should remain usable at 1920x1080 and 3840x2160.

## Implementation Checklist

### Documentation Setup

- [ ] Create `docs/sub-sprint-phase/09_frontend_interaction_console/`
- [ ] Create `target.md`
- [ ] Create `checklist.md`
- [ ] Create `errors_and_fixes.md`
- [ ] Update `docs/global_checklist.md`
- [ ] Keep all docs updated when code changes

### Frontend Architecture

- [ ] Refactor current single-page UI into `Questionnaire`, `Debug`, and `Control` tabs
- [ ] Add tab navigation and persistent active tab state
- [ ] Implement shared API/state-store layer
- [ ] Implement WebSocket reconnect handling
- [ ] Implement low-frequency state/health polling
- [ ] Ensure debug-frame refresh pauses outside Debug tab
- [ ] Add frontend event timeline

### Questionnaire Tab

- [ ] Render question text from live payload/config
- [ ] Render min/max labels from live payload/config
- [ ] Render live score bar
- [ ] Render numeric rating
- [ ] Render current phase
- [ ] Render identity/candidate message
- [ ] Implement elegant countdown ring/pulse animation
- [ ] Show `SNAPSHOT` and `COMPLETED` states cleanly
- [ ] Avoid hardcoded question sequence assumptions

### Debug Tab

- [ ] Display `/api/debug-frame`
- [ ] Show state/session/tracking/fusion data
- [ ] Show health service statuses
- [ ] Show detector/card candidate info when present
- [ ] Show hand proxy/keypoint info when present
- [ ] Show snapshot/OCR/vector/persistence status
- [ ] Show rolling debug timeline
- [ ] Handle missing debug frame with clear placeholder

### Control Tab

- [ ] Add camera settings UI
- [ ] Add camera settings API endpoints
- [ ] Add camera capability discovery
- [ ] Disable unsupported controls
- [ ] Apply settings via backend service
- [ ] Show applied/rejected settings
- [ ] Show current camera status and last error
- [ ] Add safe camera restart action if backend support exists

### Backend Integration

- [ ] Add `CameraControlService`
- [ ] Register service in app startup/context
- [ ] Extend `UIService` with camera control routes
- [ ] Keep route handlers thin
- [ ] Add status fields to `/api/health` if camera control status is separate from camera status
- [ ] Ensure unsupported camera properties degrade gracefully

### Validation

- [ ] Run static checks on frontend and backend touched files
- [ ] Run app locally with existing backend
- [ ] Verify `/api/health`, `/api/state`, `/api/debug-frame`, `/ws/score`
- [ ] Verify Debug tab receives live debug image
- [ ] Verify Questionnaire tab follows score and phase changes
- [ ] Verify countdown UI is backend-timing driven
- [ ] Verify Control tab reads current camera settings
- [ ] Verify supported settings can be applied
- [ ] Verify unsupported settings are disabled or rejected safely
- [ ] Verify UI remains readable at 1920x1080
- [ ] Verify UI scales cleanly at 3840x2160
- [ ] Run one full questionnaire session on target hardware when available

## Acceptance Criteria

### General

- [ ] The application opens into the Questionnaire tab by default.
- [ ] The user can switch between Questionnaire, Debug, and Control tabs without page reload.
- [ ] WebSocket disconnects are visible and reconnect automatically.
- [ ] The UI remains responsive while debug frames refresh.
- [ ] The UI does not require optional OCR/vector/YOLO backends to be installed.

### Questionnaire

- [ ] Current question is displayed from backend-provided context.
- [ ] Score bar updates live from `/ws/score`.
- [ ] Rating display is stable and readable.
- [ ] Countdown is visually polished and not a plain elderly-news-broadcast countdown.
- [ ] `SNAPSHOT` state shows an explicit capture/lock message.
- [ ] Completed session shows a clear completion message.
- [ ] Known and unknown candidates receive distinct messages.

### Debug

- [ ] Debug tab shows current debug overlay image.
- [ ] Debug tab shows full state/session/tracking/fusion context.
- [ ] Debug tab shows service health and degraded states.
- [ ] Debug tab makes workspace/card/hand visibility issues diagnosable.
- [ ] Debug tab handles missing debug frames without crashing or visual spam.

### Control

- [ ] Control tab lists supported camera properties.
- [ ] Unsupported properties are disabled with a reason.
- [ ] Applying a setting reports success/failure per property.
- [ ] Camera settings changes do not crash the camera loop.
- [ ] Camera restart action is either implemented safely or hidden/disabled.

### Documentation

- [ ] `target.md` describes objective, guardrails, scope, status, and non-goals.
- [ ] `checklist.md` contains scope, implementation tasks, acceptance criteria, and manual tests.
- [ ] `errors_and_fixes.md` documents all encountered frontend/backend integration issues.
- [ ] `docs/global_checklist.md` reflects the new frontend sprint status.
- [ ] Code changes without documentation updates are not considered complete.

## Manual Test Steps

### Test 1: Backend Endpoint Smoke Test

Command:

```bash
python -m app.main --config config/config.yaml
```

Then open:

```text
http://localhost:8000/
http://localhost:8000/api/health
http://localhost:8000/api/state
http://localhost:8000/api/debug-frame
http://localhost:8000/api/version
```

Expected result:

```text
The UI loads, API endpoints respond, and debug-frame returns either JPEG content or 204 when no frame is available.
```

### Test 2: WebSocket Score Test

Command:

```bash
python -m app.main --config config/config.yaml
```

Expected result:

```text
The Questionnaire tab updates score, phase, source, fusion state, candidate id, and countdown from `/ws/score`.
```

### Test 3: Debug Tab Refresh Test

Steps:

```text
1. Open Questionnaire tab.
2. Confirm debug-frame polling is paused or low-cost.
3. Switch to Debug tab.
4. Confirm the debug image refreshes.
5. Switch away from Debug tab.
6. Confirm refresh stops or drops to idle behavior.
```

Expected result:

```text
Debug frame polling only consumes resources when useful.
```

### Test 4: Camera Control Test

Steps:

```text
1. Open Control tab.
2. Load camera capabilities.
3. Change exposure or focus.
4. Apply settings.
5. Confirm applied/rejected result.
6. Confirm the live image reflects supported changes.
```

Expected result:

```text
Supported properties are applied, unsupported properties are reported without breaking the camera loop.
```

### Test 5: Full Booth Flow

Command:

```bash
python -m app.main --config config/config.yaml
```

Steps:

```text
1. Place a real business card.
2. Confirm Candidate/Identity message appears.
3. Move the card to change score.
4. Cover/release with hand and confirm fusion state remains understandable.
5. Hold still until countdown.
6. Confirm elegant countdown and snapshot transition.
7. Confirm next question appears without UI flicker.
8. Complete all questions.
```

Expected result:

```text
The visitor flow feels smooth, the operator can diagnose tracking, and camera tuning can be adjusted without leaving the browser.
```

## Explicit Non-Goals

- Do not introduce a heavy frontend framework unless the project already adopts one.
- Do not redesign backend state-machine logic in this sprint except for required UI/control endpoints.
- Do not make hand-only tracking appear as a valid session start path.
- Do not block scoring on OCR, identity, vector, or persistence work.
- Do not implement user authentication unless explicitly requested later.
- Do not implement remote/cloud dashboards.
- Do not overfit the UI to only one monitor size.

## Recommended Agent Entry Points

### Read First

```text
docs/global_checklist.md
docs/sub-sprint-phase/07_tracking_advances/target.md
docs/sub-sprint-phase/07_tracking_advances/checklist.md
docs/sub-sprint-phase/08_state_and_persistence_advances/target.md
docs/sub-sprint-phase/08_state_and_persistence_advances/checklist.md
app/services/ui_service.py
app/services/health_service.py
app/web/index.html
app/web/styles.css
app/web/app.js
```

### Create First

```text
docs/sub-sprint-phase/09_frontend_interaction_console/target.md
docs/sub-sprint-phase/09_frontend_interaction_console/checklist.md
docs/sub-sprint-phase/09_frontend_interaction_console/errors_and_fixes.md
```

### Modify Next

```text
app/web/index.html
app/web/styles.css
app/web/app.js
app/services/ui_service.py
```

### Add If Needed

```text
app/services/camera_control_service.py
app/web/js/api.js
app/web/js/state_store.js
app/web/js/questionnaire_view.js
app/web/js/debug_view.js
app/web/js/control_view.js
app/web/js/tabs.js
```

## Suggested First Implementation Order

1. Create the new sprint documentation folder and files.
2. Refactor the current UI into tabs without changing backend behavior.
3. Implement the shared frontend state store and WebSocket reconnect handling.
4. Move current score/question/debug rendering into the correct tabs.
5. Add Debug tab health/state panels and event timeline.
6. Add camera settings backend service and routes.
7. Add Control tab and connect it to the new routes.
8. Polish Questionnaire countdown and completed-state UX.
9. Validate on desktop browser.
10. Validate on target kiosk hardware.
11. Update checklist and errors/fixes after each meaningful change.

## Definition of Done

This sprint is done when:

```text
The browser UI can guide a visitor through the questionnaire, show an operator what the CV/tracking stack is doing, and adjust camera settings from the browser without leaving the running application.
```

The implementation must include updated phase documentation and a validated manual test result. If target hardware is unavailable, document that limitation clearly in `errors_and_fixes.md` and leave target validation unchecked.
