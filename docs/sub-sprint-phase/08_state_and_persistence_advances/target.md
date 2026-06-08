# Sprint Target – 08 State and Persistence Advances

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `08_state_and_persistence_advances` |
| Phase Name | `State and Persistence Advances` |
| Status | `IN_PROGRESS` |
| Last Updated | 2026-06-07 |

## Objective

Implement a config-driven questionnaire flow that stores answers and snapshots, triggers OCR/identity processing asynchronously, and keeps persistence concerns off the live tracking loop.

## Guardrail Alignment

- Questionnaire flow is config-driven and not hardcoded into one fixed top-level state sequence.
- OCR, identity resolution, vector search, and persistence must not block live scoring.
- Deterministic identity evidence wins over vector similarity.
- The system must create a temporary candidate/session before metadata is known and upgrade it later when deterministic fields appear.

## Target Scope

- Config-driven questionnaire runtime with movement gate, idle timer, countdown, snapshot trigger, and per-question context.
- `SNAPSHOT` state to persist answers, save images/crops, and hand off metadata extraction asynchronously.
- SQLite persistence for candidates, sessions, answers, and snapshots.
- OCR pipeline with PaddleOCR hook, regex extractors, heuristics, and strict non-hallucinating parser schema.
- Identity resolver with deterministic email / name+company hashing and vector lookup only as fallback evidence.
- Vector-service layer with text/image embeddings and separate text/image collections.

## Current Implementation Status

| Target Item | Status | Notes |
|---|---|---|
| Config-driven questionnaire runtime | DONE | Question definitions are read from config and written into runtime context. |
| Countdown and `SNAPSHOT` state | DONE | `TRACKING` raises snapshot requests and `SNAPSHOT` persists answers/snapshots. |
| Identity precheck before session start | DONE | `CANDIDATE_DETECTED` resolves known vs unknown candidates before questionnaire session creation. |
| SQLite persistence | DONE | Repositories and schema for candidates, sessions, answers, and snapshots are in place, including merge metadata and answer candidate links. |
| OCR metadata pipeline | DONE | PaddleOCR hook plus regex/heuristic/strict parser path are implemented with optional backend loading. |
| Deterministic identity resolver | DONE | Email hash and name+company hash IDs are preferred over temporary or vector-based matches. |
| Vector service | DONE | Separate text/image collections, per-snapshot point IDs, CLIP-first image embedding, and in-memory fallback path are implemented. |
| Async snapshot metadata processing | DONE | OCR/identity/vector work is dispatched from `SNAPSHOT` via `SnapshotProcessingService` in a background thread. |
| Runtime validation with real snapshots | NOT_DONE | Windows dev environment only received static validation in this session. |

## Explicit Non-Goals

- Blocking the tracking loop on OCR or database work.
- Auto-merging uncertain candidates from visual similarity alone.
- Inventing missing metadata in the parser stage.
- Remote/cloud persistence or a heavy multi-service backend.