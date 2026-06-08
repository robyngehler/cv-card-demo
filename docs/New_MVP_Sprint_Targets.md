# Sprint 1: Tracking-Advances

## Sprint Goal

Build a robust high-frequency interaction tracking stack that supports natural card movement by hand without requiring markers or fixtures.

This sprint combines:

```text
- Dual workspace handling
- MediaPipe hand tracking
- YOLO-based card detection interface
- Hand-card fusion with two transition phases
- Stable live score output
```

## Primary Deliverables

### 1. Dual Workspace Support

Implement separate card and hand workspaces.

Requirements:

- Card workspace remains the scoring reference.
- Hand workspace is larger and includes the lower interaction area.
- Hand measurements must be transformed into card workspace coordinates.
- Debug overlays must show both workspace rectangles.

Acceptance:

```text
- Card workspace crop still works.
- Hand workspace crop includes hand at lower work area edge.
- A hand landmark in hand crop can be transformed into normalized card score x.
```

### 2. MediaPipe Hand Tracker

Implement `MediaPipeHandTracker` and `HandProxyEstimator`.

Requirements:

- Detect hand landmarks in the hand workspace.
- Estimate index/middle finger proxy.
- Provide confidence and validity flags.
- Handle temporary landmark instability.
- Publish debug information.

Acceptance:

```text
- Index and middle finger landmarks are visible in debug overlay.
- hand_proxy_x moves smoothly when the user pushes the card.
- The tracker still sees the hand when the hand is near the lower border of the card workspace.
```

### 3. YOLO Card Detector Interface

Implement the interface and service structure for a YOLO-based card detector.

Requirements:

- Provide a `CardMeasurement` API equivalent to existing detector outputs.
- Keep contour detector as fallback until YOLO is trained/integrated.
- Support future OBB or segmentation output without changing fusion code.
- Allow detector frequency control by state.

Acceptance:

```text
- Fusion tracker can consume CardMeasurement independent of whether it came from contour or YOLO.
- Card detector source is visible in debug payload.
- Low-frequency card detector loop can run independently from high-frequency hand tracking.
```

### 4. Fusion Tracker with Two Merge Phases

Implement `CardHandFusionTracker`.

Requirements:

- Support fusion states:
  - NO_TARGET
  - CARD_OBSERVED
  - CARD_TO_HAND_MERGE
  - HAND_PROXY_ACTIVE
  - HAND_TO_CARD_MERGE
  - CARD_REACQUIRED
  - LOST_HOLD
- Prevent score jumps when switching from card to hand.
- Prevent score jumps when switching from hand back to card.
- Use score smoothing and velocity limits.
- Include `fusion_state` and `source` in every UI payload.

Acceptance:

```text
Scenario A: Card visible, no hand
  - Score follows card x.

Scenario B: Hand enters and covers card
  - Score does not jump.
  - Source changes to hand proxy.
  - Score continues to move live.

Scenario C: User releases card
  - Score does not jump to raw card x.
  - Score blends softly back to card pose.

Scenario D: Hand and card disappear
  - System enters LOST_HOLD and then IDLE according to config.
```

### 5. UI Debug Payload and Overlay

Extend UI payloads to show tracking source and fusion state.

Requirements:

- Payload includes `score`, `rating`, `state`, `fusion_state`, `source`, `question_id`, `candidate_id`.
- Debug overlay can show hand landmarks, hand proxy, card bbox, and current source.
- User-facing UI remains clean; debug info can be secondary.

Acceptance:

```text
- Developer can tell whether score came from card, hand, or merge state.
- User sees stable rating feedback.
```

## Sprint 1 Suggested Checklist

```markdown
- [ ] Add `workspace.card` and `workspace.hand` config sections
- [ ] Implement coordinate transform utilities
- [ ] Add hand workspace debug overlay
- [ ] Implement MediaPipe hand tracker service
- [ ] Implement hand proxy estimator
- [ ] Add hand proxy validity checks
- [ ] Add CardMeasurement abstraction
- [ ] Add YOLO card detector interface/stub
- [ ] Preserve contour detector as fallback
- [ ] Implement fusion state enum
- [ ] Implement card-to-hand merge
- [ ] Implement hand-to-card merge
- [ ] Add score smoothing and velocity limiting
- [ ] Extend WebSocket score payload
- [ ] Add debug overlay for fusion source
- [ ] Test hand-covered-card live scoring
- [ ] Document errors in `errors_and_fixes.md`
- [ ] Update sprint checklist after validation
```

## Sprint 1 Guardrails

- Do not add physical markers or fixtures.
- Do not make hand tracking depend on the card crop.
- Do not normalize hand x against the hand workspace directly for scoring.
- Do not hard-switch source values without merge smoothing.
- Do not block hand tracking on card detection.
- Do not let YOLO integration block the fusion tracker interface; start with interface and fallback if necessary.

---

# Sprint 2: State-and-Persistence-Advances

## Sprint Goal

Build a configurable questionnaire flow with snapshot, metadata extraction, candidate identity resolution, and persistence.

This sprint combines:

```text
- Config-driven questionnaire runtime
- Countdown and snapshot flow
- PaddleOCR metadata extraction
- Regex, heuristics, and LLM parser
- SQLite persistence
- Qdrant vector search
- Deterministic and fallback candidate recognition
```

## Primary Deliverables

### 1. Config-Driven Questionnaire Runtime

Implement a runtime that reads question definitions from config and controls phases through context.

Requirements:

- Support variable number of questions.
- Support per-question thresholds and timers.
- Track movement start, active scoring, idle time, countdown, snapshot trigger, next question, and completion.
- Keep the global state machine simple.

Acceptance:

```text
- Adding/removing a question in config changes the UI flow without code changes.
- The system can move from question 1 to question 2 after snapshot.
- The same candidate/session can continue across questions.
```

### 2. Countdown and Snapshot State

Implement or formalize `SNAPSHOT`.

Requirements:

- Countdown starts after configured idle time following sufficient movement.
- Snapshot stores answer for the current question.
- Snapshot captures best available frame/crop for metadata extraction.
- Snapshot advances to next question or completion based on config/context.

Acceptance:

```text
- User moves card for at least configured duration.
- User stops moving.
- Countdown appears.
- Answer is saved after countdown.
- Next question appears or session completes.
```

### 3. SQLite Persistence

Implement repositories for candidates, sessions, answers, and snapshots.

Requirements:

- Temporary candidate/session can be created before metadata is known.
- Answers are stored with question ID, score, rating, source, and timestamp.
- Snapshots store image path, crop path, OCR text, and extraction JSON.
- Candidate identity can be upgraded after metadata extraction.

Acceptance:

```text
- Completed question answers are persisted.
- Snapshot metadata can be linked to session and candidate.
- Temporary candidate ID can later be resolved to deterministic candidate ID.
```

### 4. PaddleOCR Metadata Extraction

Implement OCR pipeline for business card snapshots.

Requirements:

- Run OCR asynchronously or outside the high-frequency tracking path.
- Save raw OCR text.
- Support crop rectification if card bbox/OBB exists.
- Preserve original image and crop for debugging.

Acceptance:

```text
- Snapshot produces raw OCR text.
- OCR errors do not break live tracking or questionnaire progression.
- OCR results are stored and inspectable.
```

### 5. Regex + Heuristic + LLM Parser

Implement field extraction pipeline.

Requirements:

- Regex extracts email, phone, website/URL.
- Heuristics propose name, company, and role.
- LLM parser structures OCR-derived text into a strict JSON schema.
- Parser must not invent missing fields.
- Each field includes confidence and source.

Acceptance:

```text
- Email is extracted deterministically when present.
- Uncertain fields are marked with lower confidence or null.
- Parser output conforms to schema.
```

### 6. Candidate Identity Resolver

Implement deterministic and fallback identity matching.

Requirements:

- Email hash is primary identity when available.
- Name + company hash is secondary identity.
- Temporary candidate IDs are used until metadata is available.
- Existing sessions/answers can be linked or upgraded to resolved candidate.

Acceptance:

```text
- Same email resolves to same candidate_id.
- No-email cards can still create stable temporary candidates.
- Ambiguous matches do not auto-merge aggressively.
```

### 7. Qdrant Vector Store

Implement local Qdrant integration for text and image embeddings.

Requirements:

- Use separate collections initially:
  - candidate_text_embeddings
  - candidate_image_embeddings
- Text embeddings use OCR/metadata text.
- Visual embeddings use card crops.
- Vector search supports candidate similarity lookup.
- Vector results are fallback evidence, not primary identity truth.

Acceptance:

```text
- OCR text embedding can be inserted and searched.
- Card crop visual embedding can be inserted and searched.
- Similarity results are logged and linked to candidate matching decisions.
```

## Sprint 2 Suggested Checklist

```markdown
- [ ] Add questionnaire config schema
- [ ] Implement questionnaire runtime context fields
- [ ] Implement movement gate
- [ ] Implement idle timer
- [ ] Implement countdown phase
- [ ] Implement SNAPSHOT state
- [ ] Store answers in SQLite
- [ ] Store snapshots and image paths
- [ ] Implement PaddleOCR service
- [ ] Implement card crop rectification hook
- [ ] Implement regex extractor
- [ ] Implement heuristic extractor
- [ ] Implement LLM parser schema
- [ ] Add candidate identity resolver
- [ ] Add deterministic email hash ID
- [ ] Add deterministic name+company hash fallback
- [ ] Add Qdrant service
- [ ] Add text embedding service
- [ ] Add image embedding service
- [ ] Keep text and image collections separate
- [ ] Add candidate matching decision log
- [ ] Test full questionnaire flow with two questions
- [ ] Test metadata extraction on saved snapshot
- [ ] Document errors in `errors_and_fixes.md`
- [ ] Update sprint checklist after validation
```

## Sprint 2 Guardrails

- Do not hardcode the number of questions.
- Do not block score updates on OCR, database, LLM parser, or vector search.
- Do not allow LLM parser to invent metadata.
- Do not use visual embedding alone as a candidate identity match.
- Do not auto-merge uncertain candidates unless deterministic evidence is strong.
- Do not let persistence failure crash the tracking loop; report system error separately.

---

## 14. MVP Acceptance Criteria After Both Sprints

### Tracking

- [ ] Hand is detected in the larger hand workspace.
- [ ] Hand proxy maps correctly into card workspace score coordinates.
- [ ] Score follows card when only card is visible.
- [ ] Score follows hand proxy when card is occluded.
- [ ] Score does not jump when hand takes over.
- [ ] Score does not jump when card is reacquired.
- [ ] UI payload exposes `fusion_state` and `source`.

### Questionnaire

- [ ] Questions are loaded from config.
- [ ] Movement starts active scoring.
- [ ] Idle period triggers countdown.
- [ ] Snapshot stores answer.
- [ ] Next question appears after snapshot.
- [ ] Completed session is persisted.

### Metadata and Identity

- [ ] Snapshot image and crop are saved.
- [ ] OCR raw text is stored.
- [ ] Email/phone/website extraction works when present.
- [ ] LLM parser returns structured JSON without inventing missing values.
- [ ] Candidate ID is deterministic when email exists.
- [ ] Qdrant text and image embeddings can be inserted and searched.

### Reliability

- [ ] Live tracking remains responsive while OCR runs.
- [ ] Metadata failures do not break the questionnaire.
- [ ] Ambiguous identity matches do not cause unsafe merges.
- [ ] Debug overlays allow diagnosing hand/card/fusion behavior.

---

## Final Technical Decision Summary

```text
Live interaction:
  MediaPipe Hand Landmarker + Card Detector + two-phase fusion tracker

Card detection:
  YOLO-based card detector interface, contour fallback during transition

Questionnaire:
  Config-driven runtime stored in context, not hardcoded state spaghetti

Snapshot and metadata:
  PaddleOCR + regex + heuristics + strict LLM parser

Identity:
  Deterministic metadata ID first, vector similarity as fallback

Persistence:
  SQLite for structured truth, Qdrant for similarity search

Vector strategy:
  Separate text and image embeddings first
```

This design keeps the demo natural, avoids artificial markers or fixtures, and treats hand interaction as the primary expected mode rather than an annoying exception. The system becomes less dependent on fragile card contour confidence and more aligned with the real user behavior at the booth.