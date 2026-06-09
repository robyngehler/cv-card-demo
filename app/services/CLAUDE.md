# Services — `app/services/`

*Applies to all service modules under `app/services/`. Loaded automatically here.*

Each service has one clear responsibility. UI markup/JS rules live in
`app/web/CLAUDE.md`; WLED config defaults live in `config/CLAUDE.md`.

---

## CameraService (`camera_service.py`)

Owns camera open / read / reconnect. Driven by `INIT_CAM` and `RECOVERY`.

- verify `cv2` availability before opening
- open the configured camera, read and validate the first frame
- use **bounded** retry attempts — never block forever
- expose status to HealthService (camera status, OpenCV status, FPS)

---

## CameraControlService (`camera_control_service.py`)

Manages camera property controls (exposure, gain, white balance, resolution).
Separate from `CameraService` to keep stream ownership clean. Exposes an API
endpoint to adjust parameters at runtime without restarting the camera.

---

## UiService (`ui_service.py`)

FastAPI server: HTTP + WebSocket + static file serving.

Key endpoints:
```text
GET /                          — serves index.html
GET /api/health
GET /api/state
GET /api/config                — runtime config read
POST /api/config               — runtime config update
WS  /ws/status                 — state + health events
GET /live_stream               — MJPEG debug stream
GET /api/snapshots             — list captured snapshots
```

Do not add React, Vue, or build tools unless explicitly requested.

---

## HealthService (`health_service.py`)

Tracks system health state: HEALTHY, DEGRADED, ERROR. Aggregates camera status,
detector status, last error, uptime, FPS. Polled by `/api/health`.

---

## WorkspaceService (`workspace_service.py`)

Owns the workspace ROI (region of interest). Handles perspective correction and
maps the physical table area to a normalized coordinate space. The detector and
tracker work in workspace coordinates, not raw frame coordinates.

---

## CardDetectorService (`card_detector_service.py`)

Orchestrates detection: selects classical or YOLO detector based on config,
calls it each frame, publishes results to state machine context. Driven by the
tracking loop in `TRACKING` state.

---

## CandidatePrecheckService (`candidate_precheck_service.py`)

Before committing to a snapshot, performs quality checks: card stability,
confidence threshold, hand-absence, repeat-detection guard. Called from
`SNAPSHOT` state entry. Returns `PASS` or `FAIL` with a reason.

---

## SnapshotService (`snapshot_service.py`)

Captures the actual snapshot image to `data/snapshots/`. Manages filename
convention (`snapshot_<timestamp>_<session>.jpg`). Crops card region from
workspace frame. Triggered by `SNAPSHOT` state after precheck passes.

---

## SnapshotProcessingService (`snapshot_processing_service.py`)

Post-snapshot pipeline: runs OCR, identity resolution, persistence write, and
vector embedding. Runs asynchronously after snapshot capture to not block the
main tracking loop.

---

## OcrService (`ocr_service.py`)

PaddleOCR wrapper. Extracts text from a cropped card image. Results used by
`SnapshotProcessingService` for identity and persistence.

Config: `config.yaml → ocr`.

---

## IdentityService (`identity_service.py`)

Resolves whether a newly scanned card is the same as a previously seen one
(hashing / matching). Prevents duplicate session records. Config:
`config.yaml → identity`.

---

## PersistenceService (`persistence_service.py`)

SQLite-backed storage (`data/cv_card_demo.sqlite3`). Stores: candidate sessions,
snapshot references, questionnaire answers, identity hashes. Config:
`config.yaml → persistence`.

---

## QuestionnaireService (`questionnaire_service.py`)

Manages the interactive questionnaire shown after a successful scan. Q&A
definitions live in `config.yaml → questionnaire`. Uses motion/activity detection
to advance through questions.

---

## FusionTrackerService (`fusion_tracker_service.py`)

Runs the `fusion_tracker.py` pipeline (card track + hand presence) and publishes
combined state to the tracking loop. Also manages score smoothing.

---

## HandTrackerService (`hand_tracker_service.py`)

Wraps the MediaPipe hand tracking loop. Publishes hand-present / hand-absent
signal to `FusionTrackerService`. Runs in its own thread to not block the
card detector.

---

## VectorService (`vector_service.py`)

Stores card text/image embeddings in a local Qdrant collection
(`data/qdrant/`). Used for semantic deduplication and potential future search.
Config: `config.yaml → vector`. Optional — app continues if Qdrant is unavailable.

---

## WledClient (`wled_client.py`) — optional

WLED is optional and **not** required. Maps score → LED strip pattern via
WLED JSON API. Must never block camera, CV, or UI. If unreachable: log warning,
set health to `DEGRADED`, keep running.

Config: `config.yaml → wled`.
