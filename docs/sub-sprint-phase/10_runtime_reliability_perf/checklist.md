# Phase 10 — Runtime Reliability, Performance & systemd

Status: IN_PROGRESS (code complete; pending live restart + booth observation)

## Goal

Make the booth supervise, recover, and perform predictably:
1. systemd `stop`/`disable` actually control the stack.
2. Periodic latency spikes are observable (always-on timing).
3. YOLO + MediaPipe run on the right device; no silent fallback.
4. ERROR_SAFE self-heals instead of staying dead.

## systemd control

- [x] services `PartOf=cv-card-demo.target` → `stop`/`restart target` propagates
- [x] services `[Install] WantedBy=cv-card-demo.target` (NOT multi-user/graphical)
- [x] only the target is `WantedBy=multi-user.target`
- [x] `install_services.sh` disables stale per-service symlinks before reinstall,
      adds `reset-failed`, enables via the target
- [ ] live check: `stop`/`disable cv-card-demo.target` verified on the Jetson

### Why it was broken

The services were enabled directly into `multi-user.target` /
`graphical.target` and had no `PartOf=`. So `disable cv-card-demo.target` left
the services' own boot symlinks in place (kept autostarting) and
`stop cv-card-demo.target` didn't propagate to the services. Reinstall once with
`./scripts/install_services.sh` to clear the stale symlinks.

## Performance instrumentation

- [x] `app/utils/perf.py` `PerfMonitor`: per-stage p50/p95/max, periodic log
- [x] wired into the TRACKING loop (read, resize, encode_clean, card_detect,
      hand, fusion, questionnaire, publish, debug_encode, loop_total)
- [x] wired into the UI SSE snapshot build (`ui_snapshot_build`, `ui_snapshot_json`)
- [x] stages over `perf.spike_warn_ms` logged at WARNING (`PERF ... SPIKE ...`)
- [x] exposed at `/api/health` → services.perf.last_report
- [ ] live: read `PERF TRACKING ...` lines to localize the spike stage

## GPU / detectors

- [x] YOLO confirmed on GPU: health `detector.backend.device = cuda:0`, status READY
- [x] MediaPipe installed in venv (was missing → hand guard was silently off).
      Now `hand_tracker` READY (lite model, async worker thread)
- Note: on Jetson aarch64 the MediaPipe pip wheel is **CPU-only** (XNNPACK; no
  GPU delegate). It runs off the main thread + downscaled ROI + rate cap, so it
  stays off the tracking critical path. True MediaPipe-GPU is not available here.

## ERROR_SAFE recovery

- [x] ERROR_SAFE waits a backing-off interval, then retries via INIT_CAM
- [x] backoff resets on reaching IDLE; `error_safe.auto_recover` can disable it
- [ ] live: pull + replug the camera, confirm the booth recovers without restart

## Manual Test

```bash
# 1) reinstall units (clears stale symlinks), then verify control
./scripts/install_services.sh
sudo systemctl start  cv-card-demo.target && systemctl is-active cv-card-demo-backend.service
sudo systemctl stop   cv-card-demo.target && systemctl is-active cv-card-demo-backend.service   # -> inactive
sudo systemctl disable cv-card-demo.target   # reboot -> stack does NOT autostart

# 2) perf: watch the periodic PERF lines while a card is tracked
journalctl -u cv-card-demo-backend.service -f | grep PERF

# 3) recovery: unplug camera during IDLE/TRACKING, replug, confirm self-heal
```
