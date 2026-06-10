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

## Open / Hardware

- Live ESP/WLED test pending hardware on the Jetson WLAN. Expected: bar fills to
  score, recolors red→blue→cyan-green, UI stays smooth, no tracking instability.
