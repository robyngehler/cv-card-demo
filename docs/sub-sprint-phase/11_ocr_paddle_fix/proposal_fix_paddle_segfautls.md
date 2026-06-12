# Proposal v2: OCR and Snapshot Processing Stability Fixes

## Context

The snapshot-processing pipeline uses PaddleOCR, Qdrant-based vector storage, and visual feature extraction to verify whether a detected business card has already been seen. On the Jetson AGX Orin, the system shows native segmentation faults during OCR execution and a separate Qdrant upsert error during snapshot indexing. A previous attempt moved OCR into a subprocess; this contained the damage (only the worker dies now) but did not remove the root cause — the worker still crashes.

This revision merges the original proposal with a refined root-cause analysis and corrects two technical issues in the original (Qdrant point ID format, priority of the re-initialization problem).

## Root-Cause Analysis (revised)

### 1. Repeated OCR model creation — primary segfault suspect

```text
Creating model: ('PP-OCRv6_medium_det', None, None)
Creating model: ('PP-OCRv6_medium_rec', None, None)
```

These lines appear repeatedly **during normal operation**, not only at worker startup. That means the PaddleOCR pipeline is instantiated more than once per worker lifecycle. Repeated creation/destruction of Paddle C++ predictors is a known segfault pattern on aarch64 — the observed `SIGSEGV @0x0` (null-pointer dereference, no Paddle stack trace) matches teardown/re-init corruption far better than a steady-state inference crash.

This explains why the subprocess isolation alone did not help: the worker inherits the same re-initialization behavior and therefore the same crash.

Possible causes to verify, in order of likelihood:

- PaddleOCR is constructed inside the snapshot-processing path (per snapshot/request) instead of once at worker startup.
- uvicorn/FastAPI runs with `--reload` or `workers > 1`, spawning multiple app instances each creating its own pipeline.
- The OCR worker crash-loops and is restarted without backoff, making each "Creating model" a restart.
- Multiple OCR worker instances are spawned in parallel.

### 2. Concurrent / unserialized access to non-thread-safe components

Two components in the current architecture are **not thread-safe**:

- **Paddle predictors** — concurrent inference calls on the same predictor, or concurrent construction, can corrupt native state.
- **Qdrant local mode** (`QdrantClient(path=...)` / `:memory:`) — it is an in-process library without locking; concurrent upserts/searches from multiple threads (e.g. `Thread-2 (process_snapshot)`) lead to undefined behavior.

### 3. Native runtime conflicts on aarch64 (contributing factor)

Multiple native ML runtimes (Paddle, OpenCV, possibly MediaPipe/onnxruntime/YOLO) in one process each bring their own OpenMP/BLAS. Competing OpenMP runtimes and MKLDNN code paths on Cortex-A78 are a documented crash source. This is a contributing/destabilizing factor rather than the primary cause, and is mitigated by thread pinning and `enable_mkldnn=False`.

### 4. Qdrant upsert bug — independent Python-level error

```text
AttributeError: 'dict' object has no attribute 'id'
```

Plain dicts are passed to `upsert()`. The **remote** client accepts dicts (REST serialization), the **local** client requires `PointStruct` objects. This currently kills the `process_snapshot` thread on every indexing attempt. It is unrelated to the segfault and must be fixed independently.

**Additional issue not covered in the original proposal:** Qdrant point IDs must be unsigned integers or UUID strings. Candidate IDs like `tmp_2026_06_12_074324_04e08f` are **not valid point IDs** and will be rejected even after the `PointStruct` fix. A deterministic UUID must be derived from the candidate ID.

### 5. WLED timeouts — non-fatal, but blocking I/O in the hot path

```text
[WLED] update failed: timed out
```

Not a crash cause, but the timeouts recur every few hundred milliseconds, indicating synchronous HTTP calls with long timeouts inside or near the main loop. This adds latency and jitter to frame/snapshot handling.

## Proposed Fixes

### Fix 0 (verification, do this first): Find and eliminate repeated OCR initialization

Before any further architectural work:

1. Log a stack trace (`traceback.print_stack()`) at every `PaddleOCR(...)` construction and run the demo. This shows exactly which code path re-creates the pipeline.
2. Confirm uvicorn runs with a single worker and without `--reload` in the demo deployment.
3. Move construction to exactly one place: module-level or lazy singleton **inside the OCR worker**, guarded by a lock:

```python
_ocr = None
_ocr_lock = threading.Lock()

def get_ocr():
    global _ocr
    with _ocr_lock:
        if _ocr is None:
            _ocr = PaddleOCR(...)  # the ONLY construction site
        return _ocr
```

If the repeated creation is caused by crash-restart loops, the restart backoff in Fix 3 closes that loop.

### Fix 1: Correct Qdrant upsert (PointStruct + valid IDs)

```python
import uuid
from qdrant_client import models

QDRANT_NS = uuid.UUID("00000000-0000-0000-0000-00000000c0de")  # any fixed namespace

def to_point(candidate_id: str, vector, payload: dict) -> models.PointStruct:
    return models.PointStruct(
        id=str(uuid.uuid5(QDRANT_NS, candidate_id)),   # deterministic, valid UUID
        vector=[float(v) for v in vector],
        payload={**(payload or {}), "candidate_id": candidate_id},
    )

client.upsert(collection_name=collection, points=[to_point(cid, vec, payload)])
```

Notes:

- `uuid5` is deterministic: re-upserting the same candidate updates the same point (idempotent), and the original ID stays queryable via payload filter.
- For named vectors, use `vector={"image": [...]}`.

### Fix 2: Run Qdrant as a server instead of embedded local mode

The local mode is convenient but not thread-safe and not designed for concurrent app access. Recommended now (not "eventually"):

```bash
docker run -d --name qdrant -p 6333:6333 \
  -v /home/aiuser/qdrant_storage:/qdrant/storage \
  qdrant/qdrant   # official ARM64 image available
```

```python
client = QdrantClient(url="http://localhost:6333")
```

Benefits: thread-safety handled server-side, dict-format points accepted again, persistence and inspection (Web UI on :6333/dashboard) for free, and the vector store survives app crashes. Effort is low (≈1 hour including data re-indexing for a demo).

If embedded mode must be kept short-term, all Qdrant access must be serialized through a single worker thread or a global lock.

### Fix 3: Keep PaddleOCR in a dedicated `spawn` subprocess with strict lifecycle policy

The subprocess isolation from the previous attempt stays, with these requirements:

- `multiprocessing.get_context("spawn")` — **never fork.** A forked child inherits half-initialized CUDA/Paddle/OpenMP state from the parent, which itself produces `@0x0` segfaults.
- Import paddle/paddleocr **only inside the worker process**, never in the parent.
- Initialize the model exactly once at worker startup (Fix 0).
- Request/response queues, per-job timeout.
- Restart policy with backoff and crash counter:

```text
OCR request → enqueue → wait with timeout
  on timeout      → kill worker, restart with backoff
  on crash        → restart with backoff (1s, 2s, 5s, ...)
  after N crashes within M minutes → disable OCR temporarily,
                                     pipeline continues without OCR
```

- Queue depth 1–2; drop stale requests when a newer snapshot supersedes them.

### Fix 4: Environment hardening for the OCR worker

Set **before** the paddle import in the worker entrypoint:

```bash
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
```

```python
PaddleOCR(
    device="cpu",
    enable_mkldnn=False,            # MKLDNN on Cortex-A78: useless and crash-prone
    cpu_threads=2,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    # prefer mobile/lightweight det+rec model variants over PP-OCRv6_medium_*
)
```

Replace the `medium` det/rec models with mobile variants — rectified business-card crops do not need medium-tier models, and smaller models reduce memory pressure and init time on the Jetson. Verify exact model names against the installed PaddleOCR version.

### Fix 5: Event-based OCR on rectified snapshots only

OCR must never run per live frame or per UI poll (`/api/live-frame`). Target flow:

```text
camera frame
→ candidate detection / contour check
→ temporal stability check
→ perspective-rectified snapshot
→ visual duplicate check (Qdrant)
→ OCR only if identity is still ambiguous
→ final identity decision
```

OCR is a slow semantic confirmation step; the vector match is the primary real-time duplicate check.

### Fix 6: Controlled snapshot worker pipeline

Replace ad-hoc `threading.Thread(target=process_snapshot)` with a single supervised snapshot worker:

```text
Main process:        camera capture, state machine, UI API,
                     candidate detection, worker supervision
Snapshot worker:     feature extraction, Qdrant lookup/upsert,
                     duplicate decision, OCR request dispatch
OCR worker (spawn):  PaddleOCR init + inference only
```

A single snapshot worker also serializes Qdrant access by construction (relevant if embedded mode is kept temporarily).

### Fix 7: Decouple WLED updates

- Dedicated low-priority worker with "latest state wins" semantics (a 1-slot mailbox, not a growing queue).
- Short HTTP timeouts (≤ 250 ms), rate limit 5–10 Hz.
- Failures logged at debug level after the first occurrence; never propagated into the pipeline.

## Recommended Implementation Order

1. **Fix 1:** Qdrant `PointStruct` + UUID point IDs — unblocks snapshot indexing immediately.
2. **Fix 0:** Instrument and eliminate repeated PaddleOCR initialization; verify uvicorn single-worker/no-reload. *This is the most likely segfault root cause.*
3. **Fix 4:** MKLDNN off, thread pinning, lightweight models.
4. **Fix 3:** Harden the existing subprocess: spawn context confirmed, timeout, backoff, crash counter, temporary-disable mode.
5. **Fix 2:** Qdrant server in Docker.
6. **Fix 5:** Enforce event-based OCR triggering.
7. **Fix 6:** Consolidate snapshot processing into one supervised worker.
8. **Fix 7:** Decouple and rate-limit WLED.
9. Diagnostics: counters for worker restarts, OCR latency, Qdrant errors, dropped jobs.

## Medium-Term Recommendation: Replace Paddle on Jetson

PaddlePaddle on aarch64 is a recurring liability: no official GPU wheels for Jetson, fragile CPU builds, opaque native crashes. The OCR backend should be defined as a replaceable interface (input: rectified crop, output: text lines + boxes + confidences), with the following migration path:

1. **RapidOCR (`rapidocr_onnxruntime`)** — the PP-OCR models already ported to ONNX Runtime; nearly a drop-in replacement. Removes the entire Paddle C++ runtime from the system. **Preferred next step**, not merely a fallback.
2. **Custom ONNX/TensorRT export** of PP-OCR det/rec models, executed via onnxruntime-gpu (NVIDIA provides Jetson wheels) or TensorRT — enables GPU OCR coexisting cleanly with YOLO in the same CUDA context.
3. **Tesseract** as a minimal CPU fallback for rectified card crops if everything else is unavailable.

(EasyOCR is deprioritized vs. the original proposal: it pulls in a full PyTorch dependency for little benefit over RapidOCR here.)

If RapidOCR proves stable, the OCR subprocess + watchdog machinery can likely be removed entirely, simplifying the architecture.

## Expected Result

- No more thread deaths from Qdrant indexing (valid points, valid IDs).
- OCR model initialization exactly once per worker lifecycle — removing the most likely segfault trigger.
- Remaining native crashes contained to the OCR worker, with bounded restart behavior and graceful OCR-disable degradation.
- Deterministic, queue-based snapshot processing; no unserialized access to non-thread-safe components.
- WLED I/O fully decoupled from the pipeline.
- A replaceable OCR backend with a concrete migration path away from Paddle on Jetson.

## Final Recommendation

Short term: keep PaddleOCR CPU-only, fix the re-initialization (root cause), keep it aggressively isolated, and harden the environment. Run Qdrant as a server. Medium term: migrate to RapidOCR/onnxruntime — on Jetson this is the structurally sound solution, with optional GPU acceleration via onnxruntime-gpu/TensorRT, rather than waiting for community Paddle GPU builds.