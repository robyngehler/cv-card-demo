# Phase 11 — OCR Paddle Fix: Errors & Fixes

## 2026-06-12 — PaddleOCR segfaults + Qdrant upsert + exposure toggle

Three independent issues addressed per `proposal_fix_paddle_segfautls.md`.

### A) PaddleOCR `SIGSEGV @0x0` on aarch64 (proposal Fix 0/3/4)

- **Observed:** native `Segmentation fault` (no Paddle stack trace) during runs;
  `Creating model: PP-OCRv6_medium_*` lines recurred **during** operation.
- **Fix 0 finding (verified):** `PaddleOCR(...)` loads its det/rec models
  **eagerly in the constructor**, not lazily on first `.ocr()`. Therefore
  repeated "Creating model" mid-run means the constructor ran again — i.e. the
  isolated OCR worker was **crash-restarting** on inference. The model is now
  constructed exactly once per worker lifecycle; the restart loop is closed by
  the backoff policy below.
- **Fix 4 (environment hardening):** in the worker entrypoint, **before** the
  paddle import: `OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`, `FLAGS_use_mkldnn=0`. Constructor uses `device="cpu"`,
  `enable_mkldnn=False`, `cpu_threads=2`, doc-orientation / unwarping /
  textline-orientation all off, and the **mobile** det+rec models
  (`PP-OCRv5_mobile_det`, `en_PP-OCRv5_mobile_rec`) instead of `*_medium`.
  Competing OpenMP/BLAS runtimes on Cortex-A78 are the documented crash source;
  pinning + mobile models passed a 30-inference single-process stress test with
  no crash.
- **Fix 3 (subprocess + lifecycle):** OCR runs in a `mp.get_context("spawn")`
  subprocess (never fork — a fork inherits half-initialised CUDA/OpenMP state).
  Paddle is imported only inside the worker. Per-job timeout (30 s) with a
  worker-alive poll, restart with backoff (1, 2, 5, 10 s) and a sliding crash
  window: after `MAX_CRASHES=4` within `CRASH_WINDOW_S=120` the service enters
  `DISABLED` for `DISABLE_COOLDOWN_S=300`, during which the snapshot pipeline
  continues **without** OCR and auto-retries after the cooldown.
- **Verification:** end-to-end OCR OK; SIGKILL of the worker mid-flight →
  crash counted, backoff, restart, recovery call OK; 4 simulated crashes →
  `DISABLED`, `extract_text` returns `DISABLED` without touching the worker.
- **Status:** DONE (CPU). Live booth soak still recommended.

### B) Qdrant local upsert — `AttributeError: 'dict' object has no attribute 'id'`

- **Cause:** local `QdrantClient` requires `PointStruct`, not plain dicts (the
  remote REST client accepts dicts). Killed `Thread-2 (process_snapshot)` on
  every index attempt. Additionally, IDs like `tmp_2026_06_12_..._04e08f` are
  not valid Qdrant point IDs (UUID / uint64 only).
- **Fix:** wrap points in `PointStruct`; derive a deterministic `uuid5` from the
  point key (namespace `…c0de`) so re-upserts are idempotent and the original
  key stays in payload as `_point_key`. All client calls serialised behind a
  `threading.Lock` (local mode is not thread-safe).
- **Status:** DONE.

### C) V4L2 exposure toggle ignored / auto stuck on

- **Cause:** `CAP_PROP_AUTO_EXPOSURE` on V4L2 UVC cameras uses raw enum ints
  (1 = manual, 3 = aperture-priority auto). Sending `0.25` truncated to `0` in
  some OpenCV builds → another auto mode, so toggling to manual did nothing.
- **Fix:** primary encodings are now `1.0` (manual) / `3.0` (auto), with
  OpenCV-normalized `0.25`/`0.75` kept as fallbacks; `_normalize_auto_value`
  recognises both raw and normalized readbacks.
- **Status:** DONE.

## RapidOCR migration investigation (proposal medium-term option)

Tested `rapidocr-onnxruntime` 1.4.4 as the Paddle replacement. **Verdict:
not plug-and-play on this Jetson env — kept as a documented future option, not
adopted.**

- **Works:** OCR runs via ONNX Runtime (~350 ms/crop), thread-safe, text quality
  comparable to Paddle, no native segfault.
- **Blocker 1 — dependency conflicts:** pulls `opencv-python`, which collides
  with the project's `opencv-python-headless` (both own the same `cv2/` dir);
  three OpenCV packages ended up installed and a naive uninstall broke `cv2`
  (had to force-reinstall headless). Also depends on `numpy` unpinned while
  MediaPipe requires `numpy<2` (env already on numpy 2.2.6 — latent breakage).
- **Blocker 2 — no GPU out of the box:** installed `onnxruntime` exposes only
  `CPUExecutionProvider` (no CUDA). RapidOCR's touted GPU benefit needs
  `onnxruntime-gpu` (NVIDIA Jetson build), which is not a plain `pip install`.
  So on this device RapidOCR is CPU-only — no advantage over hardened Paddle.
- **Decision:** stay on hardened PaddleOCR (subprocess + backoff + temp-disable)
  for the booth. Revisit RapidOCR only with a clean env that pins
  `opencv-python-headless` + `numpy<2` and, for GPU, `onnxruntime-gpu` for
  JetPack. Removed `rapidocr-onnxruntime` + the stray `opencv-python` from the
  venv; `requirements.txt` keeps `paddleocr`.
