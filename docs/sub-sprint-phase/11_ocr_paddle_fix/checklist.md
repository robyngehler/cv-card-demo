# Phase 11 — OCR Paddle Fix: Checklist

**Goal:** Stop the PaddleOCR native segfaults and the snapshot-pipeline errors
so the candidate-detection → OCR → identity flow runs unattended at the booth.

**Scope:** OCR runtime stability, Qdrant indexing correctness, V4L2 exposure
control. Non-goals: GPU OCR, Qdrant server deployment, OCR backend swap (kept as
a documented future option).

## Tasks

- [x] Fix 0 — confirm Paddle constructs models eagerly; ensure single
      construction per worker; close the crash-restart loop via backoff.
- [x] Fix 3 — `spawn` subprocess, paddle imported only in worker, per-job
      timeout, backoff + crash counter + temporary OCR-disable degradation.
- [x] Fix 4 — env thread-pinning before import, `enable_mkldnn=False`,
      `cpu_threads=2`, doc/unwarp/textline off, mobile det+rec models.
- [x] Fix 1 — Qdrant `PointStruct` + deterministic `uuid5` IDs + access lock.
- [x] V4L2 exposure encoding (raw enum 1/3) so manual toggle works.
- [x] Investigate RapidOCR; document as not plug-and-play (see errors_and_fixes).
- [ ] Fix 2 — Qdrant server in Docker (deferred; local mode + lock for now).
- [ ] Fix 5 — enforce event-based OCR (snapshot only, never per live frame).
- [ ] Fix 6 — single supervised snapshot worker.
- [ ] Fix 7 — decouple/rate-limit WLED I/O.

## Acceptance Criteria

- [x] No segfault crashes the backend process (OCR crashes contained to worker).
- [x] Snapshot indexing no longer throws in the processing thread.
- [x] Manual exposure can be set from the UI (auto can be toggled off).
- [ ] Live booth soak (multiple scans, hand occlusion) — pending on-device run.

## Manual Test Steps

1. Start backend, place a card, let it reach SNAPSHOT.
2. Confirm `/api/health → services.ocr` shows `READY`; on repeated crashes it
   should flip to `DISABLED` and the pipeline keeps running without OCR.
3. In the control view, untoggle auto-exposure and move the exposure slider;
   confirm the image brightness changes.
4. Confirm no `AttributeError` in logs during snapshot processing.

## Status

IN_PROGRESS — core stability fixes (Fix 0/1/3/4 + exposure) DONE and verified
off-device; Fix 2/5/6/7 deferred; live booth soak pending.
