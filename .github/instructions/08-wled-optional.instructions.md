---
applyTo: "app/services/wled_client.py,config/**/*.yaml"
---

# Optional WLED Instructions

## Current Status

WLED is optional and not required for the MVP.

The primary demo path is:

```text
camera → CV → score → browser UI
```

The optional later path is:

```text
score → WLED/ESP32 → 60 LEDs
```

## MVP Config

Use:

```yaml
wled:
  enabled: false
```

## Critical Rule

WLED must not block:

- BOOT
- INIT_CAM
- camera capture
- CV tracking
- UI updates

## Later Behavior

When enabled later, WLED should behave as a non-critical output service.

If WLED is unreachable:

- log warning
- set health status to `DEGRADED`
- continue running UI and CV
- retry in background
- do not crash main app

## API Design

The future WLED client should expose simple methods:

```python
class WledClient:
    def probe(self) -> bool:
        ...

    def set_score(self, score: float) -> None:
        ...

    def set_enabled(self, enabled: bool) -> None:
        ...
```

## Rate Limiting

When implemented, WLED updates should be rate-limited.

Recommended maximum:

```text
10-20 Hz
```

Do not send oversized JSON payloads at camera frame rate unless necessary.

## Failure Policy

WLED is an output channel, not a critical dependency.

The LEDs are allowed to look pretty. They are not allowed to hold the application hostage.
