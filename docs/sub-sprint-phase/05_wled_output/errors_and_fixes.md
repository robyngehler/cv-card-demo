# Phase 05 — WLED Output: Errors & Fixes

## 2026-06-10 — Stub WledClient replaced with real output adapter

- **Context:** `app/services/wled_client.py` was a non-functional stub
  (`is_available()` only); no payloads were ever sent.
- **Fix:** `WledClient` now POSTs to `/json/state` via stdlib `urllib` with a
  bounded timeout and never raises. New `WledOutputService` maps the displayed
  score to LED count + color, builds the two-segment payload, rate-limits and
  de-duplicates updates, and runs all network I/O on a daemon worker thread so a
  slow/absent ESP never blocks tracking.
- **Integration:** single call in `UIService.publish_score` forwards the same
  score shown in the UI (`None` when not visible). No second scoring path.
- **Verification:** mapping unit-checked (0.1→6 red, 0.5→30 blue, 1.0→60
  cyan-green, idle→off); disabled→`OPTIONAL_DISABLED`; enabled+unreachable host
  → `DEGRADED` within `timeout_ms`, app continues. Status: PASS (software).

## 2026-06-11 — Segment-based output implementation

- **Context:** Hardware now divided into 2 segments: Score segment (LEDs 0–14)
  and Static segment (LEDs 15–17). Required configurable segment ID, range, and
  fill direction (high_to_low).
- **Implementation:** 
  - Config: `config.yaml` now includes `segment_id`, `start_led`, `stop_led`,
    `fill_direction`, `preserve_segments`.
  - `WledOutputService`: New `_calculate_active_range()` method handles
    high_to_low (fill from stop_led downward) and low_to_high fills.
  - Payload builder: Segments are now dynamically calculated based on active
    LED range. Inactive ranges set to black `[0,0,0]` with temporary segment IDs
    (30, 31).
- **Verification:** All payloads generate correct ranges:
  - score 0.1: 2 LEDs (13–15) ✓
  - score 0.5: 8 LEDs (7–15) ✓
  - score 1.0: all 15 LEDs (0–15) ✓
  - idle: segment off ✓
  - Color gradient: red→blue→cyan-green verified ✓
- **Status:** PASS (software). Awaiting live ESP/WLED hardware test.

## Open / Hardware

- Live ESP/WLED test pending hardware on the Jetson WLAN. Expected: segment 0
  (LEDs 0–14) fills from top-right (LED 14 downward) and recolors red→blue→cyan-green.
  Segment 1 (LEDs 15–17) remains unaffected.
