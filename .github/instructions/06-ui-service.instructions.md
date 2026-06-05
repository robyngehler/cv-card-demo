---
applyTo: "app/services/ui_service.py,app/web/**/*"
---

# UI Service Instructions

## Goal

Provide a local browser UI for the booth demo.

The UI must show:

- application status
- boot/init messages
- camera status
- live ranking/progress bar
- optional debug information

## Technology

Use simple browser technologies:

```text
FastAPI
WebSocket
HTML
CSS
Vanilla JavaScript
```

Do not add React, Vue, Svelte, or build tools unless explicitly requested.

## Backend Endpoints

Recommended endpoints:

```text
GET /
GET /api/health
GET /api/state
GET /api/version
WS  /ws/status
WS  /ws/score
```

## UI Behavior

The UI should:

- connect to WebSocket
- reconnect automatically
- display current state
- display status messages
- show score when available
- show friendly error messages
- not crash when backend reconnects

## Kiosk Mode

The UI is opened locally by a systemd-managed browser service:

```text
http://localhost:8000
```

## Status Messages

Use clear messages:

```text
System starting...
Initializing camera...
Camera ready.
Place a card on the table.
Tracking card...
Card lost. Waiting...
```

## Minimal First Version

The first UI version may be very simple:

```text
title
status text
large progress bar
numeric rating
```

No unnecessary animations, no complex assets, no heavy frontend dependencies.

The booth demo needs clarity, not a small web agency living inside the Jetson.
