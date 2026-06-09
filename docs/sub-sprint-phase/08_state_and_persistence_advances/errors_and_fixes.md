# Errors and Fixes – 08 State and Persistence Advances

This file documents relevant errors, failures, workarounds, and fixes for this phase.

---

## 2026-06-06 – Optional OCR / Vector Backends Unavailable In Windows Dev Environment

### Context

- `ocr_service`
- `vector_service`
- current environment: Windows development machine

### Observed Behavior

The current environment does not provide the optional OCR/vector stack (`paddleocr`, `qdrant-client`, `sentence-transformers`).

### Expected Behavior

The persistence and metadata slice should still initialize, keep static validation clean, and expose fallback modes without blocking the rest of the app.

### Logs / Evidence

```text
Current session constraint: Windows development environment, tests only limited / not meaningful for target-runtime CV stack.
```

### Suspected Cause

Target-runtime dependencies are intentionally not installed in the current workstation setup.

### Fix Applied

The services now load external backends lazily and fall back to schema-only OCR status, in-memory vector storage, and deterministic/hash-based embeddings when optional packages are absent.

### Verification

Command:

```bash
get_errors on app/services/ocr_service.py and app/services/vector_service.py
```

Expected/observed result:

```text
No static analysis errors; services remain available in fallback mode.
```

### Status

```text
WORKAROUND
```

---

## 2026-06-06 – Metadata Work Must Not Block Tracking

### Context

- `SNAPSHOT` state
- `snapshot_service`
- questionnaire progression

### Observed Behavior

OCR, identity resolution, vector indexing, and persistence writes could become a latency source if they run directly inside the tracking loop.

### Expected Behavior

The live score path should stay independent from OCR/persistence latency.

### Logs / Evidence

```text
Guardrail requirement: Do not block score updates on OCR, database, LLM parser, or vector search.
```

### Suspected Cause

Without an explicit snapshot handoff, metadata work would naturally accumulate in the synchronous state path.

### Fix Applied

`TRACKING` now transitions into `SNAPSHOT`, persists the immediate answer/image payload, and dispatches OCR/identity/vector work from `SnapshotService.enqueue_processing()` in a background thread.

### Verification

Command:

```bash
get_errors on app/states/snapshot.py and app/services/snapshot_service.py
```

Expected/observed result:

```text
No static analysis errors; asynchronous handoff path is in place.
```

### Status

```text
FIXED
```

---

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| 2026-06-06 | Real OCR / identity / vector validation pending | OPEN | Requires target-like environment and optional backends |

---

## 2026-06-07 – Session Start Happened Before Known/Unknown Candidate Resolution

### Context

- `IDLE_NO_CARD` / `CANDIDATE_DETECTED` / `questionnaire_service`

### Observed Behavior

The prior implementation could start a questionnaire session before any low-budget identity precheck had a chance to reuse an existing known `candidate_id`.

### Expected Behavior

The state flow should attempt a bounded identity precheck before session start so known candidates can resume and unknown candidates become temporary only after precheck failure.

### Logs / Evidence

```text
Guardrail break identified in global checklist: session start needed to happen after candidate precheck, not before it.
```

### Suspected Cause

Session creation still happened opportunistically from `TRACKING`, and `CANDIDATE_DETECTED` only confirmed visual stability.

### Fix Applied

Added `CandidatePrecheckService`, moved session creation into `CANDIDATE_DETECTED`, and made `TRACKING` use only a fallback temporary session path if that precheck step is unexpectedly missing.

### Verification

Command:

```bash
get_errors on candidate_precheck, candidate_detected, questionnaire, tracking, and main
```

Expected/observed result:

```text
No static analysis errors after the identity precheck flow was integrated.
```

### Status

```text
FIXED
```

---

## 2026-06-07 – Snapshot Service Mixed Capture And Metadata Side Effects

### Context

- `snapshot_service`
- OCR / identity / vector indexing

### Observed Behavior

`SnapshotService` both captured image data and directly orchestrated OCR, identity, persistence, and vector indexing.

### Expected Behavior

Snapshot capture should stay focused on saving frame/crop data, while metadata side effects belong to a separate processing service.

### Logs / Evidence

```text
Architecture review flagged SnapshotService._process_snapshot as too broad for the intended service boundary.
```

### Suspected Cause

The first implementation optimized for speed of delivery and accumulated follow-up responsibilities in the capture service.

### Fix Applied

Added `SnapshotProcessingService`, made `SnapshotService` responsible only for capture/save operations, and delegated asynchronous OCR/identity/vector processing through the new service.

### Verification

Command:

```bash
get_errors on snapshot_service.py and snapshot_processing_service.py
```

Expected/observed result:

```text
No static analysis errors after the snapshot-processing split.
```

### Status

```text
FIXED
```