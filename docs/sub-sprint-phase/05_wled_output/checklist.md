# Phase 05 — WLED Output

Status: IN_PROGRESS (code complete; pending live ESP/WLED hardware test)

## Goal

Mirror the already-displayed score onto a WLED LED bar:
`displayed_score -> active LED count + color -> POST /json/state -> ESP32`.
Optional, non-critical: never blocks camera, CV, or UI.

## Scope

- [x] WLED config block (`config.yaml` + `.example`)
- [x] Low-level `WledClient` (stdlib `urllib`, timeout, never raises)
- [x] `WledOutputService` (worker thread, rate limit, dedup, idle)
- [x] score -> LED count mapping
- [x] score -> red→blue→cyan-green color mapping
- [x] two-segment payload builder
- [x] health status (`/api/health` → services.wled)
- [x] manual test script `scripts/test_wled_score.py`
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
- [x] score 0.1 → ~6 LEDs, red
- [x] score 0.5 → 30 LEDs, blue `[0,80,255]`
- [x] score 1.0 → 60 LEDs, cyan-green `[0,255,170]`
- [x] idle/no-card → LEDs off
- [x] updates rate-limited (`update_hz`, default 15) + dedup
- [x] health endpoint shows WLED status
- [ ] live ESP/WLED bar fills and changes color while a card moves (HARDWARE)

## Manual Test

```bash
# config.yaml: wled.enabled can stay false; the script posts directly.
python scripts/test_wled_score.py --host http://4.3.2.1 --score 0.1   # ~6 red
python scripts/test_wled_score.py --host http://4.3.2.1 --score 0.5   # 30 blue
python scripts/test_wled_score.py --host http://4.3.2.1 --score 1.0   # 60 cyan-green
python scripts/test_wled_score.py --host http://4.3.2.1 --idle        # off
```

For live integration: set `wled.enabled: true` + `wled.host`, restart the
backend, move a card, watch the bar fill/recolor and confirm UI stays smooth.
