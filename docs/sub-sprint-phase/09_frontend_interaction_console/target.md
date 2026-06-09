# Phase Target – 09 Frontend Interaction Console

## Metadata

| Field | Value |
|---|---|
| Phase ID | `09_frontend_interaction_console` |
| Status | `IN_PROGRESS` |
| Last Updated | 2026-06-08 |

## Objective

Deliver a production-ready booth UI with three explicit tabs:

- `Questionnaire` (visitor-facing)
- `Debug` (operator/developer diagnostics)
- `Control` (camera tuning)

## Guardrails

- Keep score loop non-blocking.
- Keep session entry business-card anchored (`CANDIDATE_DETECTED`).
- Keep OCR/vector/persistence visibly asynchronous.
- Keep frontend dependency-light (vanilla JS/CSS/HTML).
- Disable unsupported camera controls instead of failing hard.

## Target Scope

- Tabbed shell and persistent active tab.
- Shared frontend state store with one score WebSocket and low-rate polling for state/health.
- Debug frame panel with refresh pause when Debug tab is inactive.
- Runtime panel and frontend event timeline.
- Control panel with camera settings read/apply, capability awareness, and safe restart endpoint.
- Polished countdown ring UX driven by backend timing when available.

## Out of Scope

- New frontend framework.
- State-machine redesign.
- Cloud dashboards/auth.
- Blocking questionnaire flow on OCR/vector completion.
