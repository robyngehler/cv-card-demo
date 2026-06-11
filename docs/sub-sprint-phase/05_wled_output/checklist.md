# Phase 05 — WLED Output

Status: IN_PROGRESS (segment-based output implemented; pending live ESP/WLED hardware test)

## Goal

Mirror the already-displayed score onto a WLED LED bar via segment-based output:
`displayed_score -> active LED count + color -> segment payload -> POST /json/state -> ESP32`.
Optional, non-critical: never blocks camera, CV, or UI.

## Scope

- [x] WLED config block with segment configuration (`config.yaml` + `.example`)
- [x] Low-level `WledClient` (stdlib `urllib`, timeout, never raises)
- [x] `WledOutputService` with segment support (worker thread, rate limit, dedup, idle)
- [x] score -> LED count mapping
- [x] score -> red→blue→cyan-green color mapping
- [x] segment-based payload builder (configurable fill direction)
- [x] segment range calculation (high_to_low and low_to_high fill)
- [x] health status (`/api/health` → services.wled)
- [x] manual test scripts (`scripts/test_wled_score.py`, `scripts/test_wled_segments.py`, `scripts/test_wled_integration.py`)
- [x] single integration point (`UIService.publish_score`)

## Non-Goals (unchanged)

No effects/animations, no MQTT/Home Assistant, no per-pixel gradients, no second
scoring path, never block on ESP availability.

## Networking

Target: Jetson joins the ESP32's own WLED access point ("WLED-AP"). WLED's AP
default address is `http://4.3.2.1` — set `wled.host` to that. Any reachable
station-mode IP works too.

## Acceptance Criteria

- [x] WLED disabled → `OPTIONAL_DISABLED`, no side effects
- [x] WLED enabled but offline → `DEGRADED`, no crash, bounded timeout
- [x] score 0.1 → ~1–2 LEDs (high_to_low fill from LED 14), red
- [x] score 0.5 → ~7–8 LEDs (high_to_low fill from LED 14), blue `[0,80,255]`
- [x] score 1.0 → all 15 LEDs (0–14), cyan-green `[0,255,170]`
- [x] idle/no-card → segment 0 off
- [x] segment 1 (static, LEDs 15–17) preserved during updates
- [x] segment-based fill direction (high_to_low) working correctly
- [x] updates rate-limited (`update_hz`, default 20) + dedup
- [x] health endpoint shows WLED status
- [ ] live ESP/WLED bar fills from top-right and changes color while a card moves (HARDWARE)

## Manual Test

Unit tests (no hardware needed):
```bash
python scripts/test_wled_segments.py     # payload generation, LED ranges
python scripts/test_wled_integration.py  # configuration, color mapping, structure
```

Integration tests (with ESP32/WLED at http://4.3.2.1):
```bash
# config.yaml: wled.enabled can stay false; the script posts directly.
python scripts/test_wled_score.py --host http://4.3.2.1 --score 0.1   # ~1–2 LEDs red
python scripts/test_wled_score.py --host http://4.3.2.1 --score 0.5   # ~7–8 LEDs blue
python scripts/test_wled_score.py --host http://4.3.2.1 --score 1.0   # all 15 LEDs cyan-green
python scripts/test_wled_score.py --host http://4.3.2.1 --idle        # segment 0 off
```

For live integration: set `wled.enabled: true` + `wled.host`, restart the
backend, move a card near the camera. Watch segment 0 (LEDs 0–14) fill from
top-right (LED 14 downward) and recolor. Confirm UI and LED bar stay in sync
and UI latency is unaffected.
