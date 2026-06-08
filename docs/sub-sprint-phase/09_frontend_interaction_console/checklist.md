# Phase Checklist – 09 Frontend Interaction Console

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `09_frontend_interaction_console` |
| Phase Name | `Frontend Interaction Console` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-08 |

## Goal

Provide a tabbed exhibition UI where visitors can complete scoring while operators can diagnose runtime state and tune camera settings directly from the browser.

## Scope

This phase includes:

- [x] Tabbed shell (`Questionnaire`, `Debug`, `Control`)
- [x] Shared frontend store + websocket reconnect strategy
- [x] Questionnaire panel with phase/status/score rendering
- [x] Cinematic countdown ring for capture phases
- [x] Debug panel with runtime key-value state and timeline
- [x] Debug-frame refresh pause outside Debug tab
- [x] Camera settings backend endpoints and control panel wiring

## Non-Goals

This phase explicitly does not include:

- [ ] Frontend framework migration
- [ ] State-machine redesign for session logic
- [ ] Cloud-based operations dashboard

## Implementation Checklist

- [x] Create `docs/sub-sprint-phase/09_frontend_interaction_console/`
- [x] Add `target.md`, `checklist.md`, `errors_and_fixes.md`
- [x] Refactor UI into tabbed interface
- [x] Add frontend state-store and timeline
- [x] Add exponential websocket reconnect
- [x] Pause debug-frame refresh outside Debug tab
- [x] Add camera control routes in `UIService`
- [x] Add `CameraControlService`
- [x] Register `camera_control` in app startup
- [x] Surface camera control status in health payload
- [x] Update `docs/global_checklist.md`
- [ ] Run full booth flow manual test on target hardware

## Acceptance Criteria

- [x] App opens with Questionnaire tab active
- [x] Tab switching works without reload
- [x] Score websocket reconnects with backoff
- [x] Debug frame polling is tab-scoped
- [x] Runtime debug panel renders state/session/tracking essentials
- [x] Control tab shows supported/unsupported camera settings
- [x] Apply response reports per-property rejected keys
- [x] Camera restart endpoint and UI action exist
- [x] `errors_and_fixes.md` updated
- [x] `docs/global_checklist.md` updated
- [ ] Verified full flow on target Jetson booth hardware

## Manual Test Steps

### Test 1: Endpoint + UI Smoke

Command:

```bash
python -m app.main --config config/config.yaml
```

Expected result:

```text
UI loads with three tabs. /api/health, /api/state, /api/version and /api/camera/* endpoints respond.
```

Status:

```text
NOT_RUN
```

### Test 2: Debug Refresh Scope

Steps:

```text
1. Open Questionnaire tab.
2. Confirm Debug panel is inactive.
3. Switch to Debug tab and watch frame age update.
4. Switch away and confirm debug polling stops.
```

Expected result:

```text
Debug frame requests run only while Debug tab is active.
```

Status:

```text
NOT_RUN
```

### Test 3: Camera Control Apply

Steps:

```text
1. Open Control tab.
2. Refresh settings.
3. Change supported properties and click Apply Settings.
4. Review applied/rejected report.
```

Expected result:

```text
Supported fields apply; unsupported fields remain disabled or are rejected safely.
```

Status:

```text
NOT_RUN
```
