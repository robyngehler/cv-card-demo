# CV-Card-Demo – WLED Integration Proposal

**Project:** CV-Card-Demo  
**Phase:** `05_wled_output`  
**Document Status:** Lean implementation proposal  
**Target Hardware:** ESP32 running WLED, 60 LED strip  
**Primary Goal:** Mirror the already displayed score from the backend/UI to WLED as a filled LED bar.  
**Design Principle:** WLED is an optional output channel. It must never block camera tracking, UI updates, or score generation.

---

## 1. Purpose

The CV pipeline already calculates and displays a score.

The WLED integration should not introduce a second scoring path.

The target flow is:

```text
displayed_score
  ↓
WLED output adapter
  ↓
ESP32 / WLED
  ↓
60 LED bar
```

The LED bar should:

- fill according to the current `displayed_score`
- map score to active LED count
- map score to a CeTI / Robotics Institute Germany inspired color scale
- keep inactive LEDs off
- fail gracefully if WLED is unavailable

---

## 2. Core Rule

The only input to WLED should be the finalized score that is already shown in the UI.

Use:

```text
displayed_score
```

Do not use:

```text
raw card x position
raw detector confidence
unfiltered tracking value
temporary candidate position
```

Reason:

> The display and the LED strip must show the same score.

If the UI shows `7/10`, the LED bar should represent the same `7/10`, not some unfiltered parallel universe where the card briefly achieved enlightenment.

---

## 3. Scope

This phase includes:

- adding WLED configuration
- adding a small `WledClient`
- adding a small `WledOutputService`
- mapping `displayed_score` to LED count
- mapping `displayed_score` to RGB color
- posting JSON updates to WLED
- adding rate limiting
- adding health status for WLED
- adding a manual test script or endpoint
- keeping WLED optional and non-critical

---

## 4. Non-Goals

This phase does not include:

- changing card detection
- changing tracking
- changing score calculation
- adding new UI scoring logic
- adding WLED effects or animations
- adding persistent WLED presets
- using MQTT
- using Home Assistant
- adding cloud services
- implementing complex per-pixel gradients
- blocking the app on ESP/WLED availability

No fancy LED religion yet. Just score in, LED bar out.

---

## 5. Proposed Data Flow

```text
Tracking / Score Logic
  ↓
displayed_score
  ↓
ScoreDisplayState
  ├── Browser UI
  └── WledOutputService
          ↓
      WledClient
          ↓
      HTTP POST /json/state
          ↓
      ESP32 / WLED
```

The WLED service reads or subscribes to the same `displayed_score` that the browser UI uses.

---

## 6. Score Convention

Recommended internal convention:

```text
displayed_score_normalized: float
range: 0.0 ... 1.0
```

Optional display convention:

```text
displayed_rating: int
range: 1 ... 10
```

Mapping:

```text
displayed_score_normalized = clamp(score, 0.0, 1.0)
displayed_rating = 1 + round(displayed_score_normalized * 9)
```

User-facing interpretation:

```text
0.1 ≈ 1/10
0.5 ≈ 5/10
1.0 = 10/10
```

For LED output, use the normalized score.

---

## 7. LED Count Mapping

For a 60 LED strip:

```text
led_count = 60
active_leds = round(displayed_score_normalized * led_count)
```

Clamp:

```text
active_leds = clamp(active_leds, 0, led_count)
```

Examples:

| Score | Rating Approx. | Active LEDs |
|---:|---:|---:|
| 0.0 | idle / no card | 0 |
| 0.1 | 1/10 | 6 |
| 0.5 | 5/10 | 30 |
| 1.0 | 10/10 | 60 |

If the app always displays at least `1/10` while tracking, then the minimum active LED count during tracking may be:

```text
active_leds = max(1, round(displayed_score_normalized * led_count))
```

For idle/no-card:

```text
active_leds = 0
```

---

## 8. Color Mapping

Requested design language:

```text
low score    → red
middle score → blue
high score   → green / cyan-green
```

Recommended anchor colors:

```python
LOW_COLOR  = (255, 20, 20)     # red
MID_COLOR  = (0, 80, 255)      # strong blue
HIGH_COLOR = (0, 255, 170)     # cyan-green / robotics style
```

Piecewise interpolation:

```text
score 0.0 ... 0.5:
  interpolate red → blue

score 0.5 ... 1.0:
  interpolate blue → cyan-green
```

Pseudo-code:

```python
def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))

def lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)

def lerp_rgb(c0: tuple[int, int, int], c1: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = clamp(t, 0.0, 1.0)
    return (
        lerp(c0[0], c1[0], t),
        lerp(c0[1], c1[1], t),
        lerp(c0[2], c1[2], t),
    )

def score_to_color(score: float) -> tuple[int, int, int]:
    score = clamp(score, 0.0, 1.0)

    if score <= 0.5:
        return lerp_rgb(LOW_COLOR, MID_COLOR, score / 0.5)

    return lerp_rgb(MID_COLOR, HIGH_COLOR, (score - 0.5) / 0.5)
```

---

## 9. WLED API Strategy

Use the WLED JSON API.

Recommended endpoint:

```text
POST http://<wled-host>/json/state
```

WLED's JSON API supports controlling device state and segments. For this project, use the smallest reliable subset:

```json
{
  "on": true,
  "bri": 160,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 30,
      "col": [[0, 80, 255]],
      "fx": 0
    },
    {
      "id": 1,
      "start": 30,
      "stop": 60,
      "col": [[0, 0, 0]],
      "fx": 0
    }
  ]
}
```

Where:

```text
active_leds = 30
led_count = 60
active color = score_to_color(displayed_score)
inactive color = black
```

Important convention:

```text
start = first LED index
stop = one past the last LED index
```

So for 60 LEDs:

```text
start = 0
stop = 60
```

covers LEDs `0 ... 59`.

---

## 10. Segment Strategy

### Recommended MVP Strategy: Two Segments

Use two segments:

```text
Segment 0: active filled part
Segment 1: inactive dark part
```

For every score update:

```text
active segment: [0, active_leds)
inactive segment: [active_leds, led_count)
```

Example:

```text
score = 0.5
active_leds = 30

Segment 0: 0  ... 30  active color
Segment 1: 30 ... 60  black
```

This is easy to implement and debug.

### Alternative Later: Individual LED Control

WLED also supports per-segment individual LED control via the `i` property.

That would allow more complex per-pixel gradients.  
Do not use it for the MVP unless the two-segment approach causes issues.

The MVP does not need per-pixel art. It needs to not embarrass us in front of visitors.

---

## 11. Idle / No-Card Behavior

When no card is detected:

```text
displayed_score = None
WLED mode = idle
```

Recommended MVP idle output:

```text
LEDs off
```

Payload:

```json
{
  "on": true,
  "bri": 80,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 60,
      "col": [[0, 0, 0]],
      "fx": 0
    }
  ]
}
```

A decorative idle animation can be added later.

---

## 12. Configuration

Add to `config.yaml`:

```yaml
wled:
  enabled: false
  host: "http://192.168.4.50" # http://4.3.2.1 # current ip addr of WLED esp32 host
  endpoint: "/json/state"
  led_count: 60
  brightness: 160
  timeout_ms: 250
  update_hz: 15
  fail_mode: "degraded"

  idle:
    mode: "off"
    brightness: 80

  colors:
    low_rgb: [255, 20, 20]
    mid_rgb: [0, 80, 255]
    high_rgb: [0, 255, 170]
```

For first real hardware testing:

```yaml
wled:
  enabled: true
  host: "http://<esp32-wled-ip>"
```

Default should remain:

```yaml
enabled: false
```

until the ESP32 is configured and reachable.

---

## 13. Modules to Add

### 13.1 `app/services/wled_client.py`

Low-level WLED HTTP client.

Responsibilities:

- build WLED URL
- send JSON payloads
- use timeout
- handle connection errors
- expose health status
- never crash the main app

Suggested API:

```python
class WledClient:
    def __init__(self, config: WledConfig, logger: Logger):
        ...

    def probe(self) -> bool:
        ...

    def post_state(self, payload: dict) -> bool:
        ...

    def set_enabled(self, enabled: bool) -> None:
        ...

    def get_status(self) -> WledStatus:
        ...
```

### 13.2 `app/services/wled_output_service.py`

Score-to-WLED adapter.

Responsibilities:

- receive `displayed_score`
- rate-limit updates
- avoid sending duplicate payloads
- map score to active LEDs
- map score to color
- build WLED segment payload
- call `WledClient`
- update health state

Suggested API:

```python
class WledOutputService:
    def update_displayed_score(self, displayed_score: float | None) -> None:
        ...

    def set_idle(self) -> None:
        ...

    def score_to_led_count(self, score: float) -> int:
        ...

    def score_to_color(self, score: float) -> tuple[int, int, int]:
        ...

    def build_payload(self, score: float | None) -> dict:
        ...
```

### 13.3 Optional: `app/score/displayed_score.py`

Only if a central score object does not already exist.

Recommended dataclass:

```python
@dataclass
class DisplayedScore:
    visible: bool
    normalized: float | None
    rating: int | None
    source_state: str
    timestamp: float
```

WLED should use this object and not calculate score directly from raw card pose.

---

## 14. Integration Point

The WLED service should be called wherever the browser UI score is already updated.

Recommended integration:

```text
ScorePublisher / UiService / TrackingState
  ↓
publish displayed_score to UI
  ↓
publish same displayed_score to WledOutputService
```

Pseudo-code:

```python
displayed_score = score_state.displayed_score_normalized

ctx.ui.publish_score(displayed_score)

if ctx.services.wled_output.enabled:
    ctx.services.wled_output.update_displayed_score(displayed_score)
```

On no card:

```python
ctx.ui.publish_status("Waiting for card")
ctx.services.wled_output.update_displayed_score(None)
```

Important:

> Do not let WLED errors propagate back into tracking or UI.

---

## 15. Rate Limiting

Recommended:

```yaml
wled:
  update_hz: 15
```

This means:

```text
minimum interval ≈ 66 ms
```

Reason:

- human-visible LED updates do not need camera FPS
- reduces WiFi traffic
- reduces ESP load
- prevents update spam

Do not update WLED at full camera frame rate unless necessary.

---

## 16. Duplicate Update Suppression

Avoid sending payloads if nothing changed.

Track:

```text
last_active_leds
last_color
last_idle_state
last_send_time
```

Only send if:

```text
active_leds changed
or color changed significantly
or idle/active state changed
or forced refresh interval elapsed
```

This keeps the ESP from becoming a tiny glowing packet victim.

---

## 17. Failure Handling

WLED must be non-critical.

If WLED is disabled:

```text
wled.status = OPTIONAL_DISABLED
do nothing
```

If WLED is enabled but unreachable:

```text
wled.status = DEGRADED
log warning
do not crash
do not block UI
do not block tracking
retry on future updates
```

If WLED returns an error:

```text
wled.status = ERROR or DEGRADED
store last_error
continue application
```

The main app continues even if:

```text
ESP32 is off
WiFi is down
WLED crashed
host IP is wrong
```

The LED strip is decorative. It is not the prime minister.

---

## 18. Health Status

Extend `/api/health`:

```json
{
  "services": {
    "wled": {
      "status": "OK",
      "enabled": true,
      "host": "http://192.168.4.50",
      "led_count": 60,
      "last_score": 0.73,
      "last_active_leds": 44,
      "last_color": [0, 176, 209],
      "last_update_age_ms": 45,
      "last_error": null
    }
  }
}
```

Disabled:

```json
{
  "services": {
    "wled": {
      "status": "OPTIONAL_DISABLED",
      "enabled": false
    }
  }
}
```

Offline:

```json
{
  "services": {
    "wled": {
      "status": "DEGRADED",
      "enabled": true,
      "last_error": "Connection timeout"
    }
  }
}
```

---

## 19. Logging

Recommended logs:

```text
[WLED] WLED output enabled host=http://192.168.4.50 led_count=60
[WLED] Probe successful
[WLED] Probe failed: <error>
[WLED] Score update score=0.50 active_leds=30 color=(0,80,255)
[WLED] Entering idle output mode
[WLED] Update failed: <error>
```

Do not log every update at INFO level once stable.

Use DEBUG for frequent updates.

---

## 20. Manual Test Plan

### Test 1: WLED Disabled

Config:

```yaml
wled:
  enabled: false
```

Command:

```bash
python -m app.main --config config/config.yaml --initial-state BOOT
curl http://localhost:8000/api/health
```

Expected result:

```text
application starts normally
tracking/UI unaffected
health shows wled.status=OPTIONAL_DISABLED
```

---

### Test 2: WLED Enabled but Offline

Config:

```yaml
wled:
  enabled: true
  host: "http://192.168.4.50"
```

With ESP32 off or wrong IP.

Expected result:

```text
application starts normally
tracking/UI unaffected
health shows wled.status=DEGRADED
logs show connection failure
no crash
```

---

### Test 3: Direct Score Test Script

Add:

```text
scripts/test_wled_score.py
```

Example commands:

```bash
python scripts/test_wled_score.py --score 0.1
python scripts/test_wled_score.py --score 0.5
python scripts/test_wled_score.py --score 1.0
python scripts/test_wled_score.py --idle
```

Expected result:

```text
0.1 → about 6 LEDs, red
0.5 → about 30 LEDs, blue
1.0 → 60 LEDs, cyan-green
idle → LEDs off
```

---

### Test 4: Live Tracking Integration

Run app normally.

Move card horizontally.

Expected result:

```text
UI score updates
LED fill updates
LED color changes red → blue → cyan-green
no visible UI slowdown
no tracking instability
```

---

## 21. Acceptance Criteria

This phase is complete when:

- [ ] WLED config exists
- [ ] `WledClient` exists
- [ ] `WledOutputService` exists
- [ ] WLED can be disabled without side effects
- [ ] WLED offline does not crash the app
- [ ] displayed score maps to active LED count
- [ ] displayed score maps to red → blue → cyan-green color
- [ ] score `0.1` lights about 6 LEDs red
- [ ] score `0.5` lights about 30 LEDs blue
- [ ] score `1.0` lights all 60 LEDs cyan-green
- [ ] idle/no-card sets LEDs off
- [ ] updates are rate-limited
- [ ] health endpoint shows WLED status
- [ ] errors are logged but non-fatal
- [ ] manual test script or endpoint exists
- [ ] documentation is updated

---

## 22. Documentation Updates Required

Create or update:

```text
docs/sub-sprint-phase/05_wled_output/checklist.md
docs/sub-sprint-phase/05_wled_output/errors_and_fixes.md
docs/global_checklist.md
```

Recommended global checklist entry:

```text
05 WLED Output → IN_PROGRESS
```

When stable:

```text
05 WLED Output → DONE
```

If ESP hardware is not yet available:

```text
05 WLED Output → BLOCKED
```

or:

```text
05 WLED Output → PARTIAL
```

depending on the chosen status labels.

---

## 23. Recommended Implementation Order

1. Add WLED config with `enabled: false`.
2. Add `WledStatus` dataclass.
3. Add `WledClient` with `post_state()` and timeout handling.
4. Add color mapping function.
5. Add score-to-LED-count mapping.
6. Add payload builder using two WLED segments.
7. Add `WledOutputService`.
8. Add health status fields.
9. Add test script for fixed scores.
10. Connect service to the existing `displayed_score`.
11. Verify disabled mode.
12. Verify offline mode.
13. Verify live ESP/WLED output.

---

## 24. Minimal Payload Examples

### 24.1 Idle / Off

```json
{
  "on": true,
  "bri": 80,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 60,
      "col": [[0, 0, 0]],
      "fx": 0
    }
  ]
}
```

### 24.2 Score 0.1

```json
{
  "on": true,
  "bri": 160,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 6,
      "col": [[255, 20, 20]],
      "fx": 0
    },
    {
      "id": 1,
      "start": 6,
      "stop": 60,
      "col": [[0, 0, 0]],
      "fx": 0
    }
  ]
}
```

### 24.3 Score 0.5

```json
{
  "on": true,
  "bri": 160,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 30,
      "col": [[0, 80, 255]],
      "fx": 0
    },
    {
      "id": 1,
      "start": 30,
      "stop": 60,
      "col": [[0, 0, 0]],
      "fx": 0
    }
  ]
}
```

### 24.4 Score 1.0

```json
{
  "on": true,
  "bri": 160,
  "seg": [
    {
      "id": 0,
      "start": 0,
      "stop": 60,
      "col": [[0, 255, 170]],
      "fx": 0
    }
  ]
}
```

---

## 25. Final Summary

The WLED integration should be a small output adapter:

```text
displayed_score → WLED payload → ESP32
```

It should not touch the CV pipeline.

It should not calculate a separate score.

It should not block the app.

It should simply mirror the displayed score as:

```text
score 0.1 → few red LEDs
score 0.5 → half bar blue
score 1.0 → full bar cyan-green
```

That is enough for the demo.

Stable, visible, slightly flashy.
A rare case where LEDs are allowed to be dramatic, but still not architecturally important.
