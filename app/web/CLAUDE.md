# Browser UI — `app/web/`

*Applies to the UI assets under `app/web/`. Loaded automatically here.*

## Goal

A local browser UI for the booth demo. Shows: application state, boot/init
messages, camera status, live ranking bar, questionnaire, diagnostics, and
configuration controls.

## Technology

HTML, CSS, vanilla JavaScript, WebSocket / REST to the FastAPI backend. No React,
Vue, Svelte, or build tools.

## File Structure

```text
app/web/
├── index.html          — entry point; loads tabs.js + view scripts
├── app.js              — main wiring: tab switching, WS connection, event routing
├── styles.css          — all styles; single file, no framework
└── js/
    ├── state_store.js          — reactive state store shared by all views
    ├── api.js                  — fetch/WS helpers (base URL, error handling)
    ├── tabs.js                 — tab navigation controller
    ├── live_view.js            — live camera stream (MJPEG) + overlay
    ├── run_view.js             — main runtime view: score bar, card status
    ├── configure_view.js       — workspace / detector / camera config UI
    ├── diagnostics_view.js     — health, FPS, service status
    ├── debug_view.js           — raw debug overlay, frame dump
    ├── control_view.js         — manual control buttons (state override)
    └── questionnaire_view.js   — interactive Q&A after successful scan
```

## Behavior

- connect to WebSocket on load; reconnect automatically on disconnect
- display current state and status messages
- show score bar when in TRACKING / SNAPSHOT states
- show questionnaire view after successful snapshot + processing
- show diagnostics tab always accessible for booth debugging

## Status Messages (run_view)

```text
System starting...
Initializing camera...
Camera ready. Place a card on the table.
Tracking card...
Preparing snapshot...
Processing...
Done — score: 7/10
```

## State Store

`state_store.js` is the single source of truth for UI state. Views subscribe
to it; they do not hold their own copies of backend state.

## Do Not

- add heavy animations that could lag on the Jetson's integrated GPU
- add a build step (webpack, vite, etc.) — keep it loadable directly
- add component frameworks — plain DOM manipulation is fine for this scope
