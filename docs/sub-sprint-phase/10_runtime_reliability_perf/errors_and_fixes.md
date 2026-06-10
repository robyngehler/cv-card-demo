# Phase 10 — Reliability/Perf/systemd: Errors & Fixes

## 2026-06-10 — No detection ever (stuck in IDLE_NO_CARD) + jerky live view

- **Observed:** after the CUDA/LD_LIBRARY_PATH fix, no detection/tracking/snapshot
  at all; state stayed `IDLE_NO_CARD`; UI "latency" oscillated ~30/~100/~800 ms;
  config changes (detector type, loop_hz, …) appeared to have no effect.
- **Cause (detection):** `models/yolov8n.pt` on this device is the *stock COCO*
  model (80 classes, no `business_card`). `YoloCardDetector` filtered every box
  by label, so YOLO could never yield a candidate. Before the CUDA fix the YOLO
  import failed and the app silently fell back to the classical detector — that
  is why detection used to work. Fixing CUDA activated the useless YOLO model
  and thereby "broke" the pipeline. Config changes looked ineffective because
  most of them only matter in TRACKING, which was never reached.
- **Cause (perf/jerkiness):** in IDLE the live frame is produced by the idle
  loop at `camera.idle_poll_interval` = 0.5 s (2 Hz) while the UI polls at
  ~12 Hz → displayed frame age oscillated 0–800 ms. Additionally no
  `CAP_PROP_BUFFERSIZE` was set, so slow polling of the 30 fps stream always
  returned stale buffered frames. Camera resolution was irrelevant — matching
  the observation that 1080p changed nothing.
- **Fix:**
  - `config.yaml`: `detector.type` → `classical`; restored tuned
    `loop_hz`/poll/SSE intervals; `idle_poll_interval` 0.5 → 0.1;
    `debug_log_every_frame` off.
  - `yolo_card_detector.py`: model is marked unavailable (with a WARNING log)
    when it lacks the configured `business_card_label` → existing classical
    fallback engages instead of silently never detecting.
  - `camera_service.py`: set `CAP_PROP_BUFFERSIZE=1`; removed stray
    `from turtle import width`.
- **Verification:** offline smoke test — YOLO guard flags COCO model
  (`available=False`, clear error), classical detector finds a synthetic card
  (`visible=True`, conf 1.00). Live booth test pending service restart.
- **Status:** IN_PROGRESS (awaiting live restart + card-on-table test).

## 2026-06-10 — `stop`/`disable cv-card-demo.target` had no effect

- **Observed:** `systemctl stop cv-card-demo.target` left the backend running;
  `disable cv-card-demo.target` still autostarted the stack after reboot.
- **Cause:** the service units were `[Install] WantedBy=multi-user.target` /
  `graphical.target` and were enabled directly, with no `PartOf=`. The target's
  `Wants=` only starts them; it neither stops them nor owns their boot symlinks.
- **Fix:** services now `PartOf=cv-card-demo.target` (+ `WantedBy=` the target
  only). Only the target is `WantedBy=multi-user.target`. `install_services.sh`
  disables stale symlinks before reinstalling and `reset-failed`s the units.
- **Verification:** `systemd-analyze verify` clean; live check pending one
  `./scripts/install_services.sh` run on the Jetson.

## 2026-06-10 — MediaPipe not installed → hand guard silently disabled

- **Observed:** `/api/health` showed `hand_tracker.UNAVAILABLE`
  (`No module named 'mediapipe'`), yet the design assumed MediaPipe was running.
- **Cause:** `mediapipe` was missing from the venv.
- **Fix:** `pip install mediapipe` (0.10.18). `hand_tracker` now READY. On
  aarch64 the wheel is CPU-only (XNNPACK), which is why it runs on a worker
  thread with a downscaled ROI and a rate cap. No GPU delegate exists for the
  pip wheel; YOLO remains the GPU consumer (`cuda:0`).
- **Verification:** combined import smoke test (cv2/torch/ultralytics/mediapipe)
  passes; `torch.cuda.is_available()` True; health shows YOLO `device=cuda:0`.

## 2026-06-10 — Periodic latency spikes (20-40 Hz → 100-500 ms)

- **Observed:** steady tracking rate with periodic spikes at a fixed cadence.
- **Action:** added always-on `PerfMonitor` timing across the TRACKING loop and
  the UI SSE snapshot build. Every `perf.log_interval_s` it logs per-stage
  p50/p95/max; stages over `spike_warn_ms` are logged at WARNING. This localizes
  the spike to a stage (e.g. `card_detect` vs `ui_snapshot_build` vs
  `debug_encode`) instead of guessing.
- **Notes for the live read:** YOLO detection is gated to `detector.loop_hz`
  (TRACKING: 3 Hz) and runs on the main thread, so a slow `card_detect` would
  spike at ~3 Hz; `ui_snapshot_build` runs at the SSE interval (~3 Hz). The PERF
  lines tell which one. The TRACKING loop also does two JPEG encodes per frame
  (clean + debug overlay) — `encode_clean` / `debug_encode` are now visible too.
- **Status:** instrumentation in place; root-cause stage to be read from
  `journalctl -u cv-card-demo-backend.service -f | grep PERF` on the booth.

## 2026-06-10 — ERROR_SAFE was a permanent dead-end

- **Observed:** after a camera disconnect the app reached ERROR_SAFE and stayed
  there forever (it returned `None`), requiring a manual restart even after the
  camera came back. systemd `Restart=always` did not help because the process
  never exits.
- **Fix:** ERROR_SAFE now waits a backing-off interval (`error_safe.retry_*`)
  and retries via INIT_CAM; the backoff resets on reaching IDLE. Configurable via
  `error_safe.auto_recover`.
- **Verification:** logic unit-reasoned; live pull/replug test pending.
