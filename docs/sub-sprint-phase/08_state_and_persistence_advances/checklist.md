# Phase Checklist – 08 State and Persistence Advances

## Phase Metadata

| Field | Value |
|---|---|
| Phase ID | `08_state_and_persistence_advances` |
| Phase Name | `State and Persistence Advances` |
| Status | `IN_PROGRESS` |
| Owner | TBD |
| Last Updated | 2026-06-07 |

## Goal

Store each questionnaire step with the related snapshot and candidate/session context while keeping metadata extraction off the latency-critical tracking path.

## Scope

This phase includes:

- [x] Config-driven questionnaire runtime and question context fields
- [x] Movement gate, idle timer, countdown, and `READY_FOR_SNAPSHOT` phase
- [x] `SNAPSHOT` state implementation
- [x] SQLite persistence for candidates, sessions, answers, and snapshots
- [x] Snapshot capture and background metadata processing dispatch
- [x] Snapshot capture and separate snapshot-processing service responsibilities
- [x] OCR pipeline hook with PaddleOCR fallback handling
- [x] Regex extraction for email, phone, and website
- [x] Heuristic extraction for name, company, and role
- [x] Strict parser schema that avoids inventing missing values
- [x] Deterministic candidate identity resolver with fallback vector evidence
- [x] Vector service with separate text/image collections and fallback storage mode
- [x] Candidate identity precheck before questionnaire session start
- [x] Resume-aware questionnaire session creation for known candidates

## Non-Goals

This phase explicitly does not include:

- [ ] Cloud database or remote vector store
- [ ] Aggressive auto-merge of uncertain candidates
- [ ] Runtime validation in the current Windows session with real booth hardware

## Implementation Checklist

- [x] Add questionnaire config schema
- [x] Implement questionnaire runtime context fields
- [x] Implement movement gate
- [x] Implement idle timer
- [x] Implement countdown phase
- [x] Implement `SNAPSHOT` state
- [x] Store answers in SQLite
- [x] Store `candidate_id` with answers in SQLite
- [x] Store snapshots and image paths
- [x] Split snapshot capture from snapshot processing responsibilities
- [x] Implement PaddleOCR service hook with optional backend loading
- [x] Implement card crop extraction hook
- [x] Implement regex extractor
- [x] Implement heuristic extractor
- [x] Implement strict parser schema
- [x] Add candidate identity resolver
- [x] Add candidate precheck service for known/unknown visitor resolution
- [x] Add deterministic email hash ID
- [x] Add deterministic name+company hash fallback
- [x] Prefix deterministic candidate IDs for debugging
- [x] Add vector service and local store fallback
- [x] Add text embedding service
- [x] Add image embedding service
- [x] Prefer CLIP image embeddings with fallback mode reporting
- [x] Keep text and image collections separate
- [x] Preserve vector history per snapshot via unique point IDs
- [x] Prevent `TEMPORARY` candidate status from overwriting stronger identities
- [x] Mark merged candidates and propagate reassignments to answers/sessions/snapshots
- [x] Add candidate matching decision capture in metadata payload
- [ ] Test full questionnaire flow with two or more questions on target hardware
- [ ] Test metadata extraction on a saved snapshot with optional backends installed
- [x] Document errors in `errors_and_fixes.md`
- [x] Update `docs/global_checklist.md`

## Acceptance Criteria

- [x] Questions are loaded from config without code changes
- [x] Movement starts active scoring and idle starts countdown
- [x] `SNAPSHOT` stores answers and image paths
- [x] Completed/in-progress session data is persisted in SQLite
- [x] OCR raw text, structured extraction JSON, and snapshot links are modeled in persistence
- [x] Candidate ID is deterministic when email or name+company exist
- [x] Known candidates are prechecked before session start and can resume instead of always starting temporary
- [x] Vector text and image collections remain separate
- [ ] Full runtime path verified with optional OCR/vector backends installed
- [x] Manual test limits for this session are documented
- [x] `errors_and_fixes.md` is updated
- [x] `docs/global_checklist.md` is updated

## Manual Test Steps

### Test 1: Static validation of state/persistence slice

Command:

```bash
get_errors on questionnaire, snapshot, OCR, identity, persistence, vector, and state integration files
```

Expected result:

```text
No static analysis errors in the modified state/persistence slice.
```

Status:

```text
PASS (2026-06-06)
```

### Test 2: Full runtime questionnaire flow

Command:

```bash
python app/main.py --config config/config.yaml
```

Expected result:

```text
The UI shows configurable questions, countdown triggers after motion+idle, SNAPSHOT stores answer/snapshot, and OCR/identity processing continues asynchronously.
```

Status:

```text
NOT_RUN in this session (Windows dev environment; optional backends and live camera validation pending)
```

## Notes

The service layer is intentionally dependency-light by default. Optional backends such as PaddleOCR, Qdrant, and sentence-transformers are loaded lazily and degrade to fallback modes so the repo remains statically valid on the current Windows development machine.
Known/unknown candidate resolution now happens before session start in `CANDIDATE_DETECTED`, while full OCR-driven upgrades still happen asynchronously after `SNAPSHOT`.