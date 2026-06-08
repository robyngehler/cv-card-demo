# CV-Card-Demo – Global MVP Checklist

## Phase Overview

| Phase | Status | Goal |
|---|---|---|
| 01 Boot | DONE | Start backend and UI reliably |
| 02 Init Camera | DONE | Open camera and read valid frames |
| 03 Workspace Calibration | DONE | Define workspace and score axis |
| 04 Card Detection | IN_PROGRESS | Detect valid business cards with stable confidence scoring |
| 05 Pose and Score Mapping | IN_PROGRESS | Publish normalized score from workspace x-position |
| 06 Tracking Stability | IN_PROGRESS | Hold tracking through short occlusions and candidate ambiguity |
| 07 Recovery | NOT_STARTED | Recover from camera/backend failures |
| 08 Deployment | IN_PROGRESS | systemd autostart and kiosk mode |
| 09 Frontend Interaction Console | IN_PROGRESS | Deliver Questionnaire/Debug/Control tabs with camera tuning and runtime diagnostics |
| 10 WLED Output | OPTIONAL | Add optional ESP32/WLED LED output |

## MVP Acceptance Criteria

- [ ] Jetson boots into the application environment
- [ ] Backend starts via systemd
- [ ] UI opens automatically in kiosk mode
- [x] Health endpoint is reachable
- [x] State machine keeps running when a state returns `None`
- [x] `BOOT` transitions to `INIT_CAM`
- [x] Camera opens successfully
- [x] OpenCV reads valid frames
- [x] Detector exposes scored candidates for tracking
- [x] Horizontal card position maps to `0.0 ... 1.0`
- [x] Browser UI can render live score updates from `/ws/score`
- [x] Short card occlusion keeps score visible for up to `tracking_max_lost_duration_s`
- [ ] Real camera tracking verified on Jetson with hand interaction
- [ ] Backend restarts after crash
- [x] WLED is optional and does not block the MVP

## Current Focus

```text
KNOWN_UNKNOWN_PRECHECK / EXHAUSTIVE_FUSION_FLOW / WINDOWS_STATIC_VALIDATION
```

Next recommended step:

```text
Install optional tracking/OCR/vector backends on the target environment and verify:
1. business-card-only candidate gating still transitions IDLE -> CANDIDATE_DETECTED -> TRACKING
2. candidate precheck resolves known vs unknown visitors before a questionnaire session starts
3. card -> hand -> card fusion keeps the displayed score continuous without release-time drift or one-frame drops
4. the questionnaire advances through countdown -> SNAPSHOT -> next question while answers and snapshots are persisted
```

## Recent Progress

| Date | Change | Status |
|---|---|---|
| 2026-06-08 | Implemented Sprint 09 tabbed frontend (Questionnaire/Debug/Control), frontend state store + timeline, tab-scoped debug frame refresh, and backend camera control endpoints/service | DONE |
| 2026-06-08 | Unified live-processing frame scaling across idle/candidate/tracking states and aligned calibration workspace validation to live-frame dimensions | DONE |
| 2026-06-07 | Moved YOLO, hand tracking, and fusion logic into CV engine modules and split snapshot processing from capture responsibilities | DONE |
| 2026-06-07 | Added candidate identity precheck before session start, resume-aware questionnaire session handling, and removed artificial card predictions from `TRACKING` | DONE |
| 2026-06-07 | Added persistence merge handling, answer candidate links, prefixed deterministic candidate IDs, vector history point IDs, and CLIP-first image embedding path with fallback status | DONE |
| 2026-06-06 | Added dual card/hand workspaces, detector service, MediaPipe hand tracker hook, fusion tracker, debug frame route, and explicit business-card candidate gate | DONE |
| 2026-06-06 | Added config-driven questionnaire runtime, `SNAPSHOT` state, SQLite persistence, OCR/identity/vector service layer, and live UI question/fusion payloads | DONE |
| 2026-06-05 | Replaced frame-count-only tracking hold with `CardTracker` time-based continuity | DONE |
| 2026-06-05 | Detector now exposes candidate list and uses area/aspect/rectangularity scoring | DONE |
| 2026-06-05 | State machine now stays in the current state when `run()` returns `None` | DONE |
| 2026-06-05 | UI score payload extended with `score`, `state`, and `source` | DONE |

## Known Blockers

| Date | Blocker | Impact | Status |
|---|---|---|---|
| 2026-06-06 | Optional backends (`mediapipe`, `paddleocr`, `qdrant-client`, `sentence-transformers`, optional YOLO) are not installed in the current Windows dev environment | Blocks runtime validation of hand/OCR/vector flows | OPEN |
| 2026-06-05 | No completed real-camera Jetson validation after tracker rewrite | Blocks marking phases 04-06 as DONE | OPEN |

## Next Recommended Step

```text
Use the target booth camera and run one full questionnaire session with a real business card.
Confirm that `CANDIDATE_DETECTED` is only entered from a business-card detection, that hand fusion preserves the displayed score during occlusion, and that snapshot/OCR/persistence complete without blocking the UI.
```

## Observations:
- the rectangular workspace interferes with the card candidates
- as soon as different lighting conditions throw somewhat rectangular shades the card detection is not stable anymore
- a user's hand breaks any candidate recognition capability
- the detection phase must remain business-card anchored; hand tracking may continue score updates only after a confirmed business-card candidate, never as an entry path into `CANDIDATE_DETECTED`
- before a questionnaire session starts, a low-budget identity precheck is now part of the intended flow so known candidates can resume instead of always starting as temporary visitors

### Card Detector Service:
- the outsourced `classical_card_detector.py` has no `detector_name` attribute -> may resutls in an error with CardPose Class (used as fallback or when config says so)
- `YoloCardDetector` redundantly checks if `primary_label` is a `business_card` (detect and normalize method), extra decision logic in normalize ?
- no given label is treated as `business_card`, dangerous with the check `is_business_card=bool(...)` when `candidate.is_business_card` (tldr: **`unknown_label != business_card_label`**)


## Suggestions for Fixes:
Most items listed below were implemented on 2026-06-07. Remaining open work is primarily target-runtime validation and heuristic quality tuning.

### Card Detector Service
- maybe we should outsoruce the `YoloCardDetector` like we did with `classical_card_detector.py` to keep consistency in "engine" vs "orchestrator service" ... the `CardPose` data class should be shared by both
- to avoid the redudant (and not **soc** conform) check in `_normalize_result` we should add a check inside `classical_card_detector.py` for early filtering like we did in `YoloCardDetector`

### Hand Tracker Service
- `HandMeasurement`, `HandLandmarkMeasurement` as well as `HandProxyEstimator` should be outsourced into `cv/`
- there should exist a class like `HandDetector`, similar to `YoloCardDetector` or `ClassicalDetector` for **soc** of "engine" vs "orchestrator service" -> some functionalities from `MediaPipeHandTracker` should flow into there
- way to evaluate service (`workspace = self.context.get_service(WorkspaceService)`) is inconsistent with `card_detector_service.py` (`workspace = self.context.get_service("workspace")`)

### Fusion Tracker Service
- outsource parts into cv/ to solve **soc** problem between "engine" and "service" with `FusionMeasurement`, `CardHandFusionTracker` and create a light-weight `CardHandFusionService`
- **IMPORTANT BUG:**
    - formal correct cases hand vs card vs both visible but state transition are **not** exhaustive
    - see state table below for all possible behavior
    - hand-only after card-only leads to `visible=False` for one frame (bc hand not stable yet, but this is wrong for UX) -> new state `CARD_TO_HAND_PENDING` needed which shows `visible=True` with last `last_displayed_score` 
    - `HAND_TO_CARD_VALIDATE` can get  if delta outside `reacquire_tolerance` and inside `ambiguous_tolerance` -> timeout needed to transition into `HAND_TO_CARD_AMBIGUOUS` 
    - `ambiguous_max_duration_s` is not really needed, since any `*_AMBIGUOUS` state is:
        ```text
        HAND_TO_CARD_AMBIGUOUS:
            At least one source is visible again,
            but the reacquired raw source does not agree with the canonical displayed score.
            The displayed score remains authoritative.
            No automatic timeout while any valid source remains visible.
        ```
    - changes:
        ```yaml
        tracking:
            fusion:
                hand_to_card:
                min_card_stable_frames: 3
                reacquire_tolerance_norm: 0.04
                ambiguous_tolerance_norm: 0.12
                allow_displayed_score_drift: false
                allow_blend_to_card_pose: false

                lost_hold:
                max_duration_s: 0.5
        ```
    - `fusion_state=NO_TARGET` should be kept consistent with the corresponding `_emit()` case
    - State Table:
        | Current State            | Card | Hand | Next State                                                | Score                  |
        | ------------------------ | ---: | ---: | --------------------------------------------------------- | ---------------------- |
        | `NO_TARGET`              | No | No | `NO_TARGET`                                               | `None`                 |
        | `NO_TARGET`              |   Yes | No | `CARD_OBSERVED`                                           | `card_x`               |
        | `NO_TARGET`              | No |   Yes | `NO_TARGET`                                               | `None`                 |
        | `NO_TARGET`              |   Yes |   Yes | `CARD_OBSERVED` first, then `CARD_TO_HAND_MERGE`          | initially `card_x`     |
        | `CARD_OBSERVED`          |   Yes | No | `CARD_OBSERVED`                                           | `card_x`, smoothed     |
        | `CARD_OBSERVED`          |   Yes |   Yes | `CARD_TO_HAND_MERGE` after stable hand                    | no jump                |
        | `CARD_OBSERVED`          | No |   Yes | `CARD_TO_HAND_PENDING` → `HAND_PROXY_ACTIVE`              | hold, then hand+offset |
        | `HAND_PROXY_ACTIVE`      | No |   Yes | `HAND_PROXY_ACTIVE`                                       | hand+offset            |
        | `HAND_PROXY_ACTIVE`      |   Yes |   Yes | `HAND_PROXY_ACTIVE`                                       | hand+offset            |
        | `HAND_PROXY_ACTIVE`      |   Yes | No | `HAND_TO_CARD_VALIDATE` / `CARD_REACQUIRED` / `AMBIGUOUS` | hold user score        |
        | `HAND_PROXY_ACTIVE`      | No | No | `LOST_HOLD`                                               | hold briefly           |
        | `HAND_TO_CARD_VALIDATE`  |   Yes | No | `CARD_REACQUIRED` or `AMBIGUOUS`                          | hold                   |
        | `HAND_TO_CARD_AMBIGUOUS` |   Yes | No | context decision / hold / retry                           | hold                   |
    
    - **Important for `LOST_HOLD`:**
        - The displayed score is the canonical anchor during LOST_HOLD. After LOST_HOLD, every reacquired raw source must be re-aligned to this anchor. Offsets must be recalculated from the anchor, never accumulated from previous offsets.
        - after any `LOST_HOLD` no new offset should be added but the prior `displayed_score` must be saved and reapplied according to the context, next to it needed attributes are:
        ```python
        lost_hold_anchor_score = displayed_score
        lost_hold_entered_from = previous_fusion_state
        lost_hold_started_at = now
        ```
        - new state cases:

        | Before      | New Measurement           | Behavior                                                       | Score                              |
        | ----------- | ----------------------- | --------------------------------------------------------------- | ---------------------------------- |
        | `LOST_HOLD` | nothing                  | hold till timeout                                       | `anchor_score`                     |
        | `LOST_HOLD` | Card only, delta small  | `CARD_REACQUIRED`                                               | stays `anchor_score`              |
        | `LOST_HOLD` | Card only, delta big   | `LOST_REACQUIRE_AMBIGUOUS`                                      | stays `anchor_score`              |
        | `LOST_HOLD` | Hand only, not stabil | `LOST_TO_HAND_PENDING`                                          | stays `anchor_score`              |
        | `LOST_HOLD` | Hand only, stabil       | new `hand_to_score_offset`, to `HAND_PROXY_ACTIVE`          | `hand + new_offset = anchor_score` |
        | `LOST_HOLD` | card + hand             | re-sync against anchor, prefer hand for live | stays `anchor_score`              |
        | `LOST_HOLD` | timeout                 | `NO_TARGET`, reset everything                                    | `None`                             |

- small but: for good **soc** the `question_id` and `candidate_id` should be removed

### Questionnaire Service
- may outsorce parts such as dataclass into new folder `functions/`, which is similar to `cv/` but for all "engine" functionalities of persistence, identity and questionnaire services which can be outsourced
- `ensure_session()` does not check `candidate_id` against changes -> old_card must lead to `return session` but new_card must lead to `new_session`
- two motion scores should be used to avoid jitter-/ slow motion false positives/negatives, one for the latest  and one for accumulative movement (`latest_motion` and `acc_question_motion`)
    ```python
    latest_motion = abs(score - last_score) >= small_motion_epsilon
    acc_question_motion = abs(score - question_start_score) >= min_motion_norm
    ```
- check for `active_duration` should be hardened, only calculated if `first_motion_time is not None` **and** `acc_question_motion > min_motion_norm`
- `stable_since` not used, maybe `idle_duration = now - stable_since` with:
    ```python
    if no_motion:
        if stable_since is None:
            stable_since = now
    else:
        stable_since = None
    ```
- maybe two new states `WAIT_FOR_STABILITY` for time before `COUNTDOWN` and `SNAPSHOT_PENDING` for `async` snapshot

### Interplay between Workspace, Snapshot, OCR, Persistence, Vector, Identity Service:
- target should be:
```text
WorkspaceService
  defines workspace frames:
  - full frame
  - card workspace
  - hand workspace
  - ggf. OCR/crop workspace

SnapshotService
  saves Frame/Crop in the right moment
  utilizes WorkspaceService for Crop/Frame transform

OcrService
  exctracts text and structured fields from Snapshot/Crop
  does not know about Sessions, Identity or Database

IdentityService
  produces candidate_id from metadata
  uses Persistence for deterministic lookup
  uses VectorService just as fuzzy fallback/suggestion

PersistenceService
  saves  Candidates, Sessions, Answers, Snapshots
  source of truth for relative data

VectorService
  save and search of Embeddings
  is-state-memory, NOT truth
```
-> the following are fragile:

#### Workspace Service
- intermixed roles of `WorkspaceStatus` and `WorkspaceDefinition`
- role of `score` is not clear between those two
- `_workspace_names()` should not create namings not explicitly mentioned in the configs
- recommended `@dataclass` structure:
```python
@dataclass
class WorkspaceDefinition:
    name: str
    mode: str
    source_frame: str
    rect_px: ...
    points_px: ...
    output_size_px: ...
    width: int
    height: int
    transform_matrix: ...
    inverse_transform_matrix: ...

@dataclass
class ScoreMappingDefinition:
    workspace_name: str = "card"
    axis: str = "x"
    invert: bool = False

@dataclass
class WorkspaceServiceStatus:
    status: str
    last_error: Optional[str]
    configured_workspaces: list[str]
```

- some parts should be outsourced into `/tools` to keep service separate from engine

#### Snapshot Service
- `_process_snapshot` does too much work on its own, main focus should only be as stated above
- `candidate_id = self.context.runtime.get("session", {}).get("candidate_id") or snapshot_record.candidate_id` is dangerous as it uses the current runtime candidate may distinct from `identity.match_candidate()`, better `candidate_id = self.context.runtime.get("session", {}).get("candidate_id") or snapshot_record.candidate_id` 
- this `candidate_id` **must** be used consequently for persistence and vector db
- extract parts into `cv/` so only raw service is left, functionalities/engines/dataclasses should live extra, f.e.
```text
SnapshotService
  capture()
  save image/crop
  return SnapshotRecord

SnapshotProcessingService
  process(snapshot_record)
  calls OCR
  calls Identity
  calls Persistence
  calls Vector
```

#### OCR Service
- `LlmBusinessCardParser` is no LLM... maybe rename to `StructuredFieldParser` and later add a real LLM
- Regex-Website may matches email john@example.com as website example.com since only `@` is filtered and not domains which are part of the email
- `company` heuristic is not stable, only takes the semantic lines besides "role" which can be anything besides the company... should either be more role-centered or an LLM should be used to evaluate role and company
- deterministic fields should be scored higher than heuristics
- extract parts into `cv/` so only raw service is left, functionalities/engines/dataclasses should live extra

#### Identity Service
- pure hash is not good for debugging, may better use `cand_email_<hash[:16]>` and `cand_name_company_<hash[:16]>`
- vector search right now is used as debug only and not for matching, maybe:
```python
if best_vector_score >= threshold and metadata.needs_review:
    decision.identity_status = "VECTOR_SUGGESTED_REVIEW"
    decision.needs_review = True
```
- extract parts into `engines/` so only raw service is left, functionalities/engines/dataclasses should live extra

#### Persistence Service
- `reassign_candidate()` **must** refresh the database, currently an answer has no `candidate_id`:
```python
self.sessions.reassign_candidate(...)
self.snapshots.reassign_candidate(...)
```
should be
```text
candidates:
  tmp candidate marked as MERGED
  merged_into_candidate_id added
```
- `ensure_candidate()` overwrites `identity_status` in conflicts, `TEMPORARY` **must not** overwrite `RESOLVED/MATCHED`
- better use UUID-Suffix for `answer_id` in case of fast saves
- change sessions, snapshots, tmp candidates as merged and allter columns:
```sql
ALTER TABLE candidates ADD COLUMN merged_into_candidate_id TEXT;
ALTER TABLE candidates ADD COLUMN merged_at TEXT;
``` 
- extract parts into `engines/` so only raw service is left, functionalities/engines/dataclasses should live extra

#### Vector Service
- if Qdrant not available, according status **must** be shown as `VECTOR MODE: IN_MEMORY_NON_PERSISTENT`
- right now `ImageEmbeddingService` does not use visual embeddings but fingerprint, **CLIP** must be used
- if one candidate has multiple snapshots, the `point_id` gets overwritten, better keep history as
```python
point_id = f"{candidate_id}:{snapshot_id}:text"
```
- extract parts into `engines/` so only raw service is left, functionalities/engines/dataclasses should live extra

### State Machhine and App Context
- **BREAK OF MVP TARGET:** 
```text
Before a questionnaire session starts, the system must attempt to resolve the visual card candidate to a semantic candidate_id using a low-frequency identity precheck.
If a known candidate is recognized, the existing candidate_id must be reused and the questionnaire may resume or skip already answered questions according to context.
If no known candidate can be resolved within the configured precheck budget, a temporary candidate_id is created and later upgraded after snapshot/OCR processing.
```
- targeted flow:
```text
IDLE_NO_CARD
  low-frequency card detection
  optional low-frequency identity precheck if stable card crop available
  ↓ visual card candidate found

CANDIDATE_DETECTED
  confirm visual stability
  run identity precheck with best available crop
  ↓

KNOWN_CANDIDATE:
  candidate_id = existing known ID
  start/resume questionnaire

UNKNOWN_CANDIDATE:
  candidate_id = tmp_...
  start new questionnaire
  later upgrade via full SNAPSHOT OCR
```
detailed:
```text
BOOT
  ↓
INIT_CAM
  ↓
CALIBRATION
  ↓
IDLE_NO_CARD
  ↓ visual card candidate
CANDIDATE_DETECTED
  ↓ visual stable + identity precheck done
TRACKING
  ↓ questionnaire pending snapshot
SNAPSHOT
  ↓ next question
TRACKING
  ↓ completed or lost
IDLE_NO_CARD
```

#### State and Service Changes
- `candidate_detected.py` state must be advanced with substates `CONFIRM_VISUAL_CANDIDATE`, `PRECHECK_IDENTITY`, `START_OR_RESUME_SESSION` and resolve known candidates via f.e.:
```python
if visual_candidate_stable:
    identity_decision = identity_precheck_service.resolve_from_frame(
        frame=best_frame,
        card_measurement=best_card_measurement,
        budget_s=identity_precheck_max_duration_s,
    )

    if identity_decision.matched:
        candidate_id = identity_decision.candidate_id
        identity_status = identity_decision.identity_status
    else:
        candidate_id = identity.create_temporary_candidate_id()
        identity_status = "TEMPORARY_PRECHECK_FAILED"

    questionnaire.ensure_session(candidate_id=candidate_id)
    session["card_identity_state"] = identity_status
    return "TRACKING"
```
- `idle.py` state can prep accordingly:
```text
IDLE_NO_CARD:
  1. detect visual card candidate
  2. store best candidate frame/crop in runtime
  3. optionally enqueue identity preview at low frequency
  4. transition to CANDIDATE_DETECTED
```
but with minmal-block settings:
```yaml
identity:
  precheck:
    enabled: true
    idle_loop_hz: 1.0
    candidate_loop_hz: 2.0
    max_duration_s: 1.0
    min_card_confidence: 0.35
    require_ocr_for_known_match: true
```
- maybe a new service `CandidatePrecheckService` could be helpful, again with **soc** of service and engine like other services
```text
Input:
  frame
  card_measurement

Does:
  crop extraction
  fast OCR or vector lookup
  identity matching

Output:
  CandidatePrecheckResult
```
and `@dataclass`:
```python
@dataclass
class CandidatePrecheckResult:
    resolved: bool
    candidate_id: str | None
    identity_status: str
    matched_on: str
    confidence: float
    snapshot_id: str | None = None
    raw_text: str | None = None
    debug: dict = field(default_factory=dict)
```
- `IdentityService` needs new API contract:
```python
def precheck_candidate(
    self,
    metadata: dict,
    persistence_service,
    vector_service=None,
    allow_vector_match: bool = False,
) -> IdentityDecision:
    ...
```
- in difference to `match_candidate()` this does not create a temporal `candidate_id` but states if it is known or not
- next to existing lookup methods inside `persistence_service.py` there should exist:
```python
find_recent_candidates(limit=...)
find_candidate(candidate_id)
get_candidate_session_progress(candidate_id)
```
- `questionnaire_service.py` must change accordingly:
```python
questionnaire.ensure_session(
    candidate_id=identity_decision.candidate_id,
    identity_status=identity_decision.identity_status,
    resume_policy="resume_incomplete_or_new"
)
```
- `CandidateDetectedState` must implement (pseudo-code):
```python
if stable_frame_count >= required_stable_frames:
    precheck = candidate_precheck.resolve(
        frame=self.best_frame,
        card_measurement=self.last_detection,
        max_duration_s=precheck_budget_s,
    )

    candidate_id = precheck.candidate_id
    if not candidate_id:
        candidate_id = identity.create_temporary_candidate_id()
        identity_status = "TEMPORARY_PRECHECK_UNRESOLVED"
    else:
        identity_status = precheck.identity_status

    questionnaire.ensure_session(
        candidate_id=candidate_id,
        identity_status=identity_status,
        now=now,
    )

    return "TRACKING"
```
- from `idly.py` to `candidate_detected.py` states there is no UI publishing after a card is detected, better:
```python
ui_service.publish_score({
    "visible": True,
    "score": result.candidate.x_normalized,
    "rating": round(result.candidate.x_normalized * 10, 1),
    "state": "IDLE_NO_CARD",
    "fusion_state": "CANDIDATE_SEEN",
    "source": "card_detector_candidate",
    ...
})
return "CANDIDATE_DETECTED"
``` 
- `candidate_detected.py` still works woth old card detector logic, no fusion **must** resolve:
```python
result = detector.detect(frame, state_name=self.name)
...
result.visible and result.candidate and result.candidate.is_business_card
```

- `tracking.py` state **must** be refined, concern is:
    - old `CardTracker` collides with new architecture to resolve `LOST_HOLD` according to hand/card recovery
    - `TrackingState` should **not** produce card-predictions but 
    ```text
    card_measurement = real card detector measurement or None
    hand_measurement = real hand tracker measurement or None
    fusion_tracker decides on LOST_HOLD/HAND/CARD/AMBIGUOUS
    ```
- `tracking.py` must resolve:
```text
read frame
get real Card Detection
get real Hand Detection
FusionTracker.update(card_measurement_or_none, hand_measurement_or_none)
Questionnaire.update(fusion_measurement)
push to UI
Snapshot
```
and **not**:
```text
CardTracker prediction as artificial CardPose
publish_last_position_during_occlusion
tracking_prediction_enabled
```
- `fusion_tracker_service.py` must resolve:
```text
LOST_HOLD
HAND_PROXY_ACTIVE
HAND_TO_CARD_VALIDATE
HAND_TO_CARD_AMBIGUOUS
LOST_TO_HAND_MERGE
```
- `session` is created in both, `TrackingState.run()` and `CandidateDetectedState`, this redundancy must be resolved:
```text
CANDIDATE_DETECTED creates temporary session
TRACKING assumes session exists
if no session: TRACKING logs warning and creates fallback session
```
- for **soc** reasons `fusion_measurement.question_id` and `fusion_measurement.candidate_id` should be removed for:
```python
"question_id": questionnaire_context.get("question_id")
"candidate_id": questionnaire_context.get("candidate_id")
```
- **maybe** bad UX with backstep to `CANDIDATE_DETECTED` after *every* question, can lead to flicker, better:
```text
completed:
  IDLE_NO_CARD / COMPLETE
not completed and same session active:
  TRACKING
not completed but target lost:
  CANDIDATE_DETECTED
```
```python
if progression.get("completed"):
    return "IDLE_NO_CARD"

if self.context.runtime.get("last_fusion_measurement", {}).visible:
    return "TRACKING"

return "CANDIDATE_DETECTED"
```
- danger with busy_loop if `next_state is None` for too long (sleep?)

#### App Context Changes
- `_default_runtime` and `_default_session_runtime` are semantically not clear, resolve better naming and check that `runtime["session"]` is the **only** place for:
```text
session_id
candidate_id
identity_status / card_identity_state
question_index
current_question_id
phase
answers
completed
``` 
- `runtime["last_candidate"]` and `runtime["last_card_measurement"]` stay as visual measurement data only

### UI 
- should act accordingly to candidate check:
```json
{
  "state": "CANDIDATE_DETECTED",
  "fusion_state": "IDENTITY_PRECHECK",
  "source": "card_crop_ocr",
  "visible": true,
  "score": null,
  "message": "Recognizing card..."
}
```
- if knwon:
```json
{
  "message": "Welcome back",
  "candidate_id": "cand_email_abcd...",
  "identity_status": "MATCHED_EMAIL"
}
```
- if unknown:
```json
{
  "message": "New visitor",
  "candidate_id": "tmp_...",
  "identity_status": "TEMPORARY_PRECHECK_UNRESOLVED"
}
```


## Open Implementations and Application Details:
### UI
- browser should open and current UI should be displayed
- debug frame route and UI panel are now implemented; target-environment validation is still pending for the live feed path
- use-case is an exhibition stand, the UI should look professional but customer friendly
    - the visitor is guided through configurable evaluation questions; question text, countdown, source, and fusion state are published to the UI
    - the recognized card acts as evaluation slider, with hand-card fusion allowed only after a confirmed business-card anchor
    - after idle state (~3s) after the card was recognized **and** moved for at least 1s a count down appears and then transitions into `SNAPSHOT`
    - afterwards the next question appears via questionnaire runtime/config, not hardcoded state logic
- browser should enable recropping of the visible workspace as well as other camera settings (quality, lightning, ...)
- browser should display different **system** error types and recovery hints (only heavy system failures)

### States and Context
- `SNAPSHOT` state is now implemented for answer persistence and metadata pipeline triggering
- the state comes after tracking state and returns into `CANDIDATE_DETECTED` for the next question or `IDLE_NO_CARD` when the session completes
- the `context` now carries questionnaire session fields (`question_index`, `current_question_id`, `phase`, countdown/session metadata)
- identity precheck now resolves known vs unknown candidates before session creation in `CANDIDATE_DETECTED`
- card candidates should be equipped with a `candidate_id` field, being stored to allow
    - separation of different customers coming after each other
    - if after x/n questions a candidate is lost and state goes into `LOST_HOLD` and `IDLE_NO_CARD` but the same candidate appears again, the questionnaire can be resumed
    - for this a feature extraction and vector database path is now scaffolded with deterministic ID priority and vector fallback only

### Detection & Card Tracker
- there must be a SOC for 1. tracking and 2. detecting candidates
    - tracking is now more stable and confidence agnostic once a business-card anchor exists, since while moving a card it may get occluded by the customer's hand
    - recognizing the card serves metadata extraction for `last_candidate_id` and a short `snapshot` of the customer's data (Name, Email, ...)
- tracking loop should be high frequency (>20 Hz) and the detection & metadata extraction should take place
    - in a low frequency loop in `IDLE_NO_CARD` (2-5 Hz, depending on hardware constraints)
    - once in a `SNAPSHOT` state
    - in a mid frequency loop in `LOST_HOLD` (5-10 Hz, depending on hardware constraints)
    - `CANDIDATE_DETECTED` must remain detector-driven and business-card-only; hand tracking is never a valid substitute for detection
  - `TRACKING` no longer fabricates predicted card poses; it now uses only real card measurements, real hand measurements, and fusion-state decisions

### Database
- for storing metadata the `SNAPSHOT` state should utilize an sql and may vector database
- it stores:
    - **readable** candidate/customer metadata from the snapshot (Email, Name, Company, ...) in the sql db
    - **feature-like** metadata for the detection process in the vector db, use-cases would be fast reconstruction of known candidates to avoid doubled questionnaires
    - questionnaire evaluation statistics per candidate/customer
- main key should be a `candidate_id` for the classic database

