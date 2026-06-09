# New MVP Guardrails Proposal

**Project:** CV-Card-Demo  
**Scope:** Robust interaction tracking, questionnaire flow, metadata extraction, persistence, and candidate recognition  
**Status:** Proposal / Implementation Guardrails  
**Primary Goal:** Keep the booth demo interaction smooth and credible while avoiding fragile assumptions about continuously visible card contours.

---

## 1. Executive Summary

The current classical card-contour tracking approach is not sufficient for the real interaction pattern of the demo. The visitor is expected to move a business card with their hand, and during most of the relevant interaction the hand will partially or fully interfere with the card shape. This means card contour confidence may legitimately drop to near zero during normal operation.

Therefore, hand occlusion must not be treated as a short exceptional failure that can be bridged with frame interpolation or a simple lost-frame timeout. It is part of the expected interaction model.

The new MVP architecture separates three responsibilities:

```text
1. High-frequency interaction tracking
   - Provides live score updates.
   - Uses hand-card fusion.
   - Must remain stable even when the card detector is temporarily unreliable.

2. Low-/mid-frequency card recognition and metadata extraction
   - Detects/crops the card when possible.
   - Extracts visitor metadata from snapshots.
   - Creates or resolves candidate identities.

3. Config-driven questionnaire and persistence flow
   - Controls questions, countdowns, snapshots, resume behavior, and completion.
   - Must not be hardcoded into one fixed linear demo path.
```

The business card remains the visible interaction object, but the live score should be driven by a fusion tracker that can switch smoothly between card pose and hand pose without visual score jumps.

No fixed visual markers, no physical card holder, and no special fixture should be introduced. These would reduce the natural demo effect.

---

## 2. Key Product Constraints

### 2.1 Must-Haves

- The visitor moves a normal business card or similar card naturally by hand.
- The live score must remain responsive while the card is moved.
- Hand interference is expected and must be supported as normal operation.
- The UI must not flicker between detected/no-card during interaction.
- The score must not jump when switching between hand-based tracking and card-based tracking.
- The number of questions and their flow must be configurable.
- Metadata extraction and candidate identification must run in the background and must not block live scoring.
- The system must remain explainable and debuggable for agentic development in VS Code.

### 2.2 Explicit Non-Goals

- Do not rely on colored markers, ArUco tags, AprilTags, stickers, card holders, rails, or fixtures.
- Do not treat hand occlusion as a rare short-term tracking failure.
- Do not use contour tuning as the primary path to solve occlusion.
- Do not block UI scoring on OCR, vector search, database writes, or LLM parsing.
- Do not make vector similarity the primary identity authority when deterministic metadata exists.

---

## 3. Updated Conceptual Architecture

```text
Camera Frame Buffer
  |
  |--> Card Workspace Crop
  |      |
  |      |--> YOLO Card Detector / Card Pose Estimator
  |      |--> Snapshot Cropper / Rectifier
  |
  |--> Hand Workspace Crop
  |      |
  |      |--> MediaPipe Hand Landmarker
  |      |--> Hand Proxy Estimator
  |
  |--> Fusion Tracker
  |      |
  |      |--> Live norm_x score
  |      |--> source / fusion_state debug payload
  |
  |--> Questionnaire Runtime
  |      |
  |      |--> question state
  |      |--> countdown state
  |      |--> snapshot trigger
  |
  |--> Snapshot / Metadata Pipeline
         |
         |--> PaddleOCR
         |--> Regex + heuristics
         |--> LLM parser
         |--> Identity resolver
         |--> SQLite + Qdrant
```

The card detector is no longer the single authority for live interaction. It is one measurement source. The hand tracker is another measurement source. The fusion tracker decides which source drives the score and how transitions are smoothed.

---

## 4. Workspace Model

The system should use two related but distinct workspaces.

### 4.1 Card Workspace

Purpose:

- Strictly cropped to the actual visible working area.
- Used for card detection, card scoring reference, snapshot crops, and score normalization.
- The horizontal score axis is defined here.

Example:

```yaml
workspace:
  card:
    mode: "manual_rect"
    source_frame: "camera"
    rect_px:
      x: 80
      y: 60
      width: 560
      height: 360
    score_axis: "x"
    invert_score_axis: false
```

### 4.2 Hand Workspace

Purpose:

- Slightly larger than the card workspace.
- Includes the lower edge area where the visitor's hand may be visible while pushing the card.
- Used only for hand landmark detection.
- Hand landmarks must be transformed back into the card workspace coordinate system before score fusion.

Example:

```yaml
workspace:
  hand:
    mode: "manual_rect"
    source_frame: "camera"
    rect_px:
      x: 40
      y: 20
      width: 600
      height: 440
    normalize_against: "card"
```

### 4.3 Coordinate Rule

All final measurements must use the card workspace coordinate system.

```text
hand crop coordinates
  -> full camera frame coordinates
  -> card workspace coordinates
  -> normalized score x in [0.0, 1.0]
```

This rule is non-negotiable. Otherwise, card measurements and hand measurements will not be comparable.

---

## 5. Hand Tracking Model

### 5.1 Selected Approach

Use MediaPipe Hand Landmarker as the first implementation target.

Reason:

- It provides a rigged hand representation with landmarks.
- It can detect index and middle finger positions.
- It is suitable for estimating the user's intended card movement while the card itself is partially occluded.

### 5.2 Hand Proxy

The first hand proxy should assume that most visitors push the card with index and middle finger.

Use the following landmarks:

```text
index_tip      = 8
index_pip      = 6
middle_tip     = 12
middle_pip     = 10
wrist          = 0    # fallback/reference only
```

Recommended weighted proxy:

```python
hand_proxy_x = (
    0.30 * index_tip_x +
    0.30 * middle_tip_x +
    0.20 * index_pip_x +
    0.20 * middle_pip_x
)

hand_proxy_y = (
    0.30 * index_tip_y +
    0.30 * middle_tip_y +
    0.20 * index_pip_y +
    0.20 * middle_pip_y
)
```

Why not only fingertips?

- Fingertips can jitter.
- Fingertips may be partly occluded by the card edge or by perspective.
- PIP joints are often more stable.

### 5.3 Hand Proxy Validity Checks

A hand proxy should only be considered valid if:

- At least index and middle finger landmarks are available with sufficient confidence.
- The index/middle finger distance is within a plausible range.
- The proxy lies inside or near the card workspace after coordinate transformation.
- The proxy does not jump beyond a configurable velocity limit.
- The hand is not too far from the last known card or score region unless the session is just starting.

Example:

```yaml
tracking:
  hand:
    enabled: true
    model: "mediapipe_hand_landmarker"
    min_detection_confidence: 0.5
    min_tracking_confidence: 0.5
    max_proxy_velocity_norm_per_s: 2.0
    max_distance_from_card_norm: 0.35
    fallback_order:
      - "index_middle_proxy"
      - "index_only_proxy"
      - "palm_center_proxy"
      - "last_stable_hand_proxy"
```

---

## 6. Card Detection Model

### 6.1 Updated Direction

Move away from relying primarily on classical contour detection for robust card recognition.

The contour detector may remain as a debug fallback or initial baseline, but the preferred direction is a small YOLO-based card detector if hardware performance allows it.

### 6.2 Role of the Card Detector

The card detector should support:

- Candidate detection.
- Card position measurement when visible.
- Reacquisition after hand movement.
- Snapshot crop proposals.
- OCR preprocessing.
- Metadata extraction support.

The card detector should not be the only source for high-frequency live scoring.

### 6.3 Recommended YOLO Path

Initial target:

```text
YOLO detect class:
  - business_card
```

Better target:

```text
YOLO OBB class:
  - business_card as oriented bounding box
```

Optional later:

```text
YOLO segmentation classes:
  - business_card
  - hand
```

### 6.4 Card Detector Frequency

```text
IDLE_NO_CARD:       2-5 Hz
CANDIDATE_DETECTED: 5-10 Hz
TRACKING:           1-5 Hz, depending on hardware
SNAPSHOT:           immediate / best-frame capture
```

Card detection may run lower frequency than hand tracking because the live score does not depend only on card detection.

---

## 7. Fusion Tracker

### 7.1 Problem to Solve

If the system switches directly from card x-position to hand x-position, or from hand x-position back to card x-position, the displayed score can jump. This is unacceptable because the visitor may set a rating while holding the card, then release it, and the score would suddenly change.

A second unacceptable behavior is slow score drift after release. Even if the transition is smooth, the visitor may perceive it as the system changing their selected rating after they already stopped interacting.

Therefore, the fusion tracker must include two explicit transition phases:

```text
1. Card -> Hand transition
2. Hand -> Card validation
```

The goal is strict continuity of the displayed score. The system must not blindly trust whichever detector currently has the highest confidence. Instead, hand-based tracking and card-based tracking must be connected through an explicit transition offset.

### 7.2 Fusion States

```text
NO_TARGET
  No usable card or hand measurement.

CARD_OBSERVED
  Card is visible and used as primary source.

CARD_TO_HAND_MERGE
  Hand becomes stable while card was previously primary.
  A hand-to-score offset is initialized so the score does not jump.

HAND_PROXY_ACTIVE
  Hand proxy drives the score using the learned transition offset.
  Card detector may have confidence near zero.

HAND_TO_CARD_VALIDATE
  Hand disappears or becomes unreliable while card becomes visible again.
  The system validates whether the card pose matches the last hand-proxy score after applying the existing offset logic.
  The displayed score must not drift toward a conflicting card pose.

CARD_REACQUIRED
  Card is stable again and can become primary source only if it agrees with the current displayed score within tolerance.

LOST_HOLD
  Neither card nor hand is reliable.
  Keep score briefly, then return to IDLE or wait according to context.
```

### 7.3 Card -> Hand Merge

Situation:

```text
Card is visible.
Hand enters.
Card becomes partially or fully occluded.
```

Process:

1. Store the last stable card-based score.
2. Wait until the hand proxy is stable for a small number of frames.
3. Compute a hand-to-score offset.
4. Switch score source to hand proxy without changing the displayed score.

Formula:

```python
anchor_score = last_card_norm_x
hand_to_score_offset = anchor_score - hand_proxy_norm_x
score = hand_proxy_norm_x + hand_to_score_offset
```

Expected result:

* No visible score jump when the hand takes over.
* Live score continues while the user pushes the card.
* The hand proxy becomes a continuation of the last known card pose, not an independent score source.

### 7.4 Hand -> Card Validation

Situation:

```text
User releases the card.
Hand disappears or becomes unreliable.
Card becomes visible again.
```

Important principle:

The displayed score at release time is considered the visitor's selected score. The system must not slowly blend or drift toward a newly detected card pose if that pose would change the selected rating.

The only acceptable transition is from the last offset-corrected hand pose to a card pose that already agrees with it within a small tolerance.

Process:

1. Store the last displayed hand-based score.
2. Store the last hand proxy position and the active hand-to-score offset.
3. Wait until the card pose is stable for a small number of frames.
4. Compare the newly visible card score with the last displayed score.
5. If the card score is within tolerance, accept the card as reacquired.
6. If the card score is outside tolerance, keep the displayed score stable and mark the transition as ambiguous instead of blending toward the card.

Recommended behavior:

```python
last_displayed_score = last_hand_proxy_norm_x + hand_to_score_offset
card_score = newly_visible_card_norm_x

delta = abs(card_score - last_displayed_score)

if delta <= reacquire_tolerance_norm:
    score = last_displayed_score
    fusion_state = "CARD_REACQUIRED"
    card_score_correction = card_score - last_displayed_score
    # Optional: update internal card alignment slowly, but do not move the displayed score.
else:
    score = last_displayed_score
    fusion_state = "HAND_TO_CARD_AMBIGUOUS"
    # Do not blend toward the card pose.
    # Wait for context decision: snapshot, keep current answer, retry tracking, or LOST_HOLD.
```

Expected result:

* No sudden score jump after the visitor lets go.
* No slow score drift after the visitor lets go.
* The displayed score remains the value the visitor set during interaction.
* Card reacquisition only restores the card as a tracking source if it agrees with the current score.
* A large mismatch is treated as an ambiguity, not as a correction target.

### 7.5 Handling Reacquisition Mismatch

A mismatch can happen when:

```text
- the hand tracker followed the wrong hand position,
- the card detector reacquired the wrong rectangular object,
- the visitor released the card while it was still sliding,
- the card pose is noisy or partially occluded,
- another card-like object enters the workspace.
```

In these cases, the fusion tracker must not change the displayed score automatically.

Recommended policy:

```text
Small mismatch:
  Accept card reacquisition.
  Keep displayed score unchanged.
  Optionally update internal alignment.

Medium mismatch:
  Keep displayed score unchanged.
  Continue using last score while waiting for a more stable card or hand measurement.

Large mismatch:
  Mark tracking as ambiguous.
  Keep displayed score unchanged.
  Let questionnaire context decide whether to snapshot, hold, retry, or return to IDLE.
```

The displayed score is user-facing state. Detector disagreement is internal diagnostic state.

### 7.6 Fusion Configuration

```yaml
tracking:
  fusion:
    card_to_hand:
      min_hand_stable_frames: 2
      hand_takeover_blend_s: 0.10
      max_initial_offset_norm: 0.35

    hand_to_card:
      min_card_stable_frames: 3
      reacquire_tolerance_norm: 0.04
      ambiguous_tolerance_norm: 0.12
      allow_displayed_score_drift: false
      allow_blend_to_card_pose: false

    ambiguous_reacquire:
      max_duration_s: 0.75
      fallback: "keep_score_and_defer_to_context"

    lost_hold:
      max_duration_s: 0.5

    smoothing:
      score_ema_alpha: 0.35
```

### 7.7 UI Payload Requirements

Every score update should include debug source data.

Example:

```json
{
  "score": 0.73,
  "rating": 7.3,
  "state": "TRACKING",
  "fusion_state": "HAND_PROXY_ACTIVE",
  "source": "hand_proxy_with_card_anchor",
  "question_id": "experience",
  "candidate_id": "tmp_2026_06_05_001"
}
```

During ambiguous hand-to-card validation:

```json
{
  "score": 0.73,
  "rating": 7.3,
  "state": "TRACKING",
  "fusion_state": "HAND_TO_CARD_AMBIGUOUS",
  "source": "last_confirmed_user_score",
  "question_id": "experience",
  "candidate_id": "tmp_2026_06_05_001",
  "debug": {
    "card_score": 0.81,
    "last_hand_offset_score": 0.73,
    "delta": 0.08,
    "reacquire_tolerance_norm": 0.04
  }
}
```

This makes user-facing behavior and developer debugging much easier.

The UI must always prefer the stable displayed score over raw detector reacquisition values. Raw card pose changes after release are diagnostic information, not automatic user-facing score updates.

---

## 8. Questionnaire Runtime

### 8.1 Design Principle

Do not hardcode the question flow into fixed Python state transitions.

The exact number of questions and the exact flow may change. Therefore, the questionnaire runtime should be driven by context and configuration.

### 8.2 Global State Machine

The global state machine should remain simple:

```text
BOOT
INIT_CAM
CALIBRATION
IDLE_NO_CARD
CANDIDATE_DETECTED
TRACKING
SNAPSHOT
LOST_HOLD
COMPLETE
ERROR
```

### 8.3 Context-Driven Questionnaire Phase

Within `TRACKING`, the questionnaire can maintain a runtime phase:

```text
WAIT_FOR_MOVEMENT
ACTIVE_SCORING
COUNTDOWN
READY_FOR_SNAPSHOT
NEXT_QUESTION
DONE
```

These do not necessarily need to be full top-level states. They can live in the context and be interpreted by `TRACKING`, `SNAPSHOT`, and related services.

### 8.4 Context Fields

Recommended fields:

```python
context.session.session_id
context.session.candidate_id
context.session.question_index
context.session.current_question_id
context.session.current_score
context.session.last_motion_time
context.session.first_motion_time
context.session.stable_since
context.session.countdown_started_at
context.session.phase
context.session.answers
context.session.card_identity_state
```

### 8.5 Questionnaire Config

```yaml
questionnaire:
  questions:
    - id: "experience"
      label: "How was your experience?"
      min_label: "0"
      max_label: "10"
      min_motion_norm: 0.03
      active_motion_duration_s: 1.0
      idle_before_countdown_s: 3.0
      countdown_s: 3.0
      snapshot_on_confirm: true

    - id: "team"
      label: "How was the team?"
      min_label: "0"
      max_label: "10"
      min_motion_norm: 0.03
      active_motion_duration_s: 1.0
      idle_before_countdown_s: 3.0
      countdown_s: 3.0
      snapshot_on_confirm: true
```

### 8.6 Expected Interaction Flow

```text
1. Card or hand-card interaction is detected.
2. Temporary session is created.
3. Question 1 is shown.
4. Visitor moves card.
5. Score updates live using fusion tracker.
6. Visitor stops moving.
7. Countdown appears after configured idle time.
8. Snapshot state stores answer and optionally captures card image.
9. Next question appears.
10. The same card/session continues unless context rules say otherwise.
11. After final question, session is completed.
```

---

## 9. Snapshot, OCR, and Field Extraction

### 9.1 Snapshot State

A `SNAPSHOT` state should be added or formalized.

Responsibilities:

- Store the answer for the current question.
- Capture best available frame or card crop.
- Trigger OCR and metadata extraction asynchronously.
- Update candidate identity if metadata becomes available.
- Advance to the next question or complete the session.

### 9.2 OCR Pipeline

Use PaddleOCR as the robust OCR path.

Pipeline:

```text
SNAPSHOT
  -> select best frame / crop
  -> card crop rectification
  -> PaddleOCR raw text extraction
  -> regex extraction
  -> heuristic extraction
  -> LLM parser
  -> structured metadata JSON
  -> persistence
```

### 9.3 Regex Extraction

Regex should handle high-confidence deterministic fields:

```text
- email
- phone
- website
- URL
```

These fields should be preferred over LLM guesses.

### 9.4 Heuristic Extraction

Heuristics should propose:

```text
- name
- company
- role/title
```

Examples:

```text
Name:
  - likely person-name line
  - not email, URL, phone, or address

Company:
  - large/central/upper text line
  - repeated branding text

Role:
  - line containing engineer, manager, lead, researcher, professor, CEO, CTO, etc.
```

### 9.5 LLM Parser

The LLM parser should only structure and normalize OCR-derived information.

It must not invent missing fields.

Required schema example:

```json
{
  "name": {
    "value": "Max Mustermann",
    "confidence": 0.74,
    "source": "llm_from_ocr"
  },
  "company": {
    "value": "ACME Robotics",
    "confidence": 0.82,
    "source": "heuristic_plus_llm"
  },
  "email": {
    "value": "max.mustermann@acme.de",
    "confidence": 0.99,
    "source": "regex"
  },
  "needs_review": false
}
```

If the OCR result is poor, the parser must return uncertainty rather than hallucinated contact data.

---

## 10. Identity and Re-Identification

### 10.1 Identity Principle

Use deterministic metadata first. Use embeddings only as fallback or similarity support.

Vector search must not override strong deterministic identity evidence.

### 10.2 Candidate ID Strategy

```text
If email exists:
  candidate_id = hash(normalized_email)

Else if name + company exist:
  candidate_id = hash(normalized_name + normalized_company)

Else:
  candidate_id = temporary UUID
```

Temporary candidate IDs can later be upgraded or merged when metadata extraction succeeds.

### 10.3 Re-Identification Strategy

Matching order:

```text
1. Exact email hash match
2. Normalized name + company match
3. Fuzzy metadata match
4. Text embedding similarity
5. Visual embedding similarity
6. Keep as separate candidate if uncertain
```

### 10.4 Why Visual Embedding Is Fallback Only

Visually similar cards do not necessarily belong to the same person. Multiple employees from the same company may have almost identical card layouts.

Therefore, CLIP-like visual embeddings may help find similar card snapshots, but they should not be sufficient alone to merge identities.

---

## 11. Database and Vector Store

### 11.1 SQL Database

Use SQLite for the MVP unless project constraints require a server database.

Recommended tables:

```sql
CREATE TABLE candidates (
  candidate_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  name TEXT,
  company TEXT,
  email TEXT,
  email_hash TEXT,
  phone TEXT,
  website TEXT,
  metadata_confidence REAL,
  identity_status TEXT NOT NULL
);

CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  candidate_id TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  state TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id)
);

CREATE TABLE answers (
  answer_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  score REAL NOT NULL,
  rating REAL NOT NULL,
  source TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE snapshots (
  snapshot_id TEXT PRIMARY KEY,
  candidate_id TEXT,
  session_id TEXT,
  image_path TEXT NOT NULL,
  crop_path TEXT,
  ocr_text TEXT,
  extraction_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id),
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
```

### 11.2 Vector Store

Use Qdrant locally for vector search.

Keep text and image embeddings separated at first:

```text
candidate_text_embeddings
candidate_image_embeddings
```

This is easier to debug than mixing modalities too early.

### 11.3 Text Embeddings

Use a small, fast sentence-transformer for OCR text and normalized metadata.

Recommended first target:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Purpose:

- Similar OCR text matching.
- Similar name/company/role strings.
- Recovery from OCR variations.

### 11.4 Visual Embeddings

Use CLIP-like image embeddings for card crop similarity.

Purpose:

- Similar card layout lookup.
- Fallback signal when OCR is weak.
- Debugging and candidate review.

Do not use visual similarity as the only merge criterion.

---

## 12. Service Structure

Recommended files/services:

```text
app/services/
  camera_service.py
  workspace_service.py

  hand_tracker_service.py
    - MediaPipeHandTracker
    - HandMeasurement
    - HandProxyEstimator

  card_detector_service.py
    - YoloCardDetector
    - ContourCardDetector fallback
    - CardMeasurement

  fusion_tracker_service.py
    - CardHandFusionTracker
    - FusionState
    - ScoreSmoother

  questionnaire_service.py
    - ConfigDrivenQuestionnaireRuntime
    - QuestionDefinition
    - SessionPhase

  snapshot_service.py
    - SnapshotCapture
    - CardCropRectifier
    - BestFrameSelector

  ocr_service.py
    - PaddleOcrService
    - RegexFieldExtractor
    - HeuristicFieldExtractor
    - LlmBusinessCardParser

  identity_service.py
    - CandidateIdentityResolver
    - CandidateMatcher

  vector_service.py
    - QdrantVectorStore
    - TextEmbeddingService
    - ImageEmbeddingService

  persistence_service.py
    - SQLiteCandidateRepository
    - SQLiteSessionRepository
```

Dataclasses / DTOs should be explicit and small.

Example:

```python
@dataclass
class HandMeasurement:
    visible: bool
    proxy_x: float | None
    proxy_y: float | None
    confidence: float
    landmarks: dict[str, tuple[float, float]]
    timestamp: float

@dataclass
class CardMeasurement:
    visible: bool
    center_x: float | None
    center_y: float | None
    confidence: float
    bbox: object | None
    source: str
    timestamp: float

@dataclass
class FusionMeasurement:
    score: float
    rating: float
    fusion_state: str
    source: str
    confidence: float
    timestamp: float
```

---

## 13. Sprint Plan

The implementation should be grouped into two larger agentic sprints. Each sprint has enough scope to produce a testable system increment without creating ten tiny command cycles before anything useful can be validated.

see `New_MVP_Sprint_Targets.md` for sprint context.

