# CV-Card-Demo – Workspace Calibration and Card Detection MVP

**Project:** CV-Card-Demo  
**Sprint / Phase:** `03_workspace_calibration_and_card_detection_mvp`  
**Application States:** `CALIBRATION`, `IDLE_NO_CARD`, `CANDIDATE_DETECTED`, later `TRACKING`  
**Document Status:** Detailed implementation draft  
**Target Platform:** NVIDIA Jetson Orin NX, Ubuntu 22.04.5 LTS, JetPack 6.1, Jetson Linux R36.4.x  
**Primary Goal:** Define a stable workspace from the camera image and detect a flat card inside that workspace using a simple classical OpenCV pipeline.  
**WLED:** Not part of this sprint. It remains optional and non-blocking.

---

## 1. Purpose

The system currently reaches:

```text
BOOT
  ↓
INIT_CAM
  ↓
IDLE_NO_CARD
```

The next goal is to make `IDLE_NO_CARD` useful by adding:

1. **Workspace calibration**
   - Define the active table/workspace area.
   - Crop or transform the raw camera image into a stable workspace image.
   - Define the score axis.

2. **Classical card detection**
   - Detect a business card or similar flat rectangular card inside the workspace.
   - Estimate simplified 2D pose:
     - `x`
     - `y`
     - `theta_deg`
     - `width`
     - `height`
     - `confidence`
   - Calculate `x_normalized` in the range `0.0 ... 1.0`.

---

## 2. Sprint Decision

Calibration and detection may be implemented in the same sprint.

However, they should remain technically separated:

```text
Sprint 03: Workspace Calibration + Card Detection MVP
  ├── 03a Workspace Calibration
  └── 03b Classical Card Detection
```

Recommended documentation layout:

```text
docs/sub-sprint-phase/03_workspace_calibration/
├── checklist.md
└── errors_and_fixes.md

docs/sub-sprint-phase/04_card_detection/
├── checklist.md
└── errors_and_fixes.md
```

Reason:

> Workspace calibration defines where to look. Detection defines what to look for.

Combining both into one monolithic module would make debugging unpleasant. And we are already using computer vision, so there is no need to increase the suffering voluntarily.

---

## 3. Updated State Flow

Current flow:

```text
BOOT
  ↓
INIT_CAM
  ↓
IDLE_NO_CARD
```

Recommended new flow:

```text
BOOT
  ↓
INIT_CAM
  ↓
CALIBRATION
  ↓
IDLE_NO_CARD
  ↓
CANDIDATE_DETECTED
  ↓
TRACKING
```

For this sprint, `TRACKING` may be minimal or still partly stubbed.

The sprint is successful once the system can:

```text
calibrate workspace
wait for card
detect plausible card candidate
calculate x_normalized
```

---

## 4. Scope

This sprint includes:

- adding a `CALIBRATION` state
- adding workspace configuration
- validating workspace configuration
- creating a workspace crop or perspective transform
- storing workspace metadata in health status
- creating a classical OpenCV card detector
- adding a `CardPose` / `CardCandidate` data structure
- running detection inside `IDLE_NO_CARD`
- transitioning from `IDLE_NO_CARD` to `CANDIDATE_DETECTED`
- publishing basic detector status through health/UI
- keeping WLED disabled or optional
- documenting progress and errors

---

## 5. Non-Goals

This sprint does not include:

- ArUco-based automatic calibration
- interactive calibration GUI
- camera intrinsic calibration
- lens undistortion
- YOLO/SAM/deep-learning detection
- TensorRT inference
- WLED LED output
- final UI polish
- multi-camera support
- production-grade object tracking
- database or cloud logging

Do not add advanced features until the simple OpenCV pipeline works reliably.

---

## 6. Why Calibration First?

Card detection without workspace calibration may detect irrelevant objects:

```text
table edges
hands
cables
keyboard edges
paper sheets
reflections
shadows
ambitious coffee stains
```

A calibrated workspace gives the detector clear boundaries:

```text
Only search here.
Only this region matters.
This axis maps to score.
Everything outside is ignored.
```

This makes detection:

- faster
- simpler
- more stable
- easier to debug

---

## 7. Workspace Calibration MVP

### 7.1 Calibration Strategy

Use config-based manual calibration first.

Do not implement automatic ArUco calibration yet.

Supported MVP modes:

```text
manual_rect
manual_quad
```

### 7.2 `manual_rect`

`manual_rect` uses a simple rectangular crop in raw camera pixel coordinates.

Example config:

```yaml
workspace:
  mode: "manual_rect"
  source_frame: "camera"
  rect_px:
    x: 80
    y: 60
    width: 480
    height: 340
  score_axis: "x"
  invert_score_axis: false
```

Behavior:

```text
workspace_frame = raw_frame[y:y+height, x:x+width]
```

Advantages:

- easiest to implement
- good enough for first tests
- easy to debug

Limitations:

- no perspective correction
- assumes the camera is close to top-down

### 7.3 `manual_quad`

`manual_quad` uses four source points and warps the selected workspace into a rectangular top-down image.

Example config:

```yaml
workspace:
  mode: "manual_quad"
  source_frame: "camera"
  points_px:
    top_left: [80, 60]
    top_right: [560, 60]
    bottom_right: [560, 400]
    bottom_left: [80, 400]
  output_size_px:
    width: 640
    height: 400
  score_axis: "x"
  invert_score_axis: false
```

Behavior:

```text
raw frame
  ↓
cv2.getPerspectiveTransform(...)
  ↓
cv2.warpPerspective(...)
  ↓
workspace_frame
```

Recommended approach:

```text
Start with manual_rect.
Add manual_quad only if the simple crop is not sufficient.
```

---

## 8. `CALIBRATION` State

### 8.1 Purpose

`CALIBRATION` validates and prepares the workspace.

It answers:

```text
Can the application produce a valid workspace frame from the current camera frame?
```

Success:

```text
CALIBRATION → IDLE_NO_CARD
```

Failure due to invalid config:

```text
CALIBRATION → ERROR_SAFE
```

Temporary camera/frame failure:

```text
CALIBRATION → RECOVERY
```

### 8.2 `enter(ctx)`

Responsibilities:

- set state to `CALIBRATION`
- set substate to `CALIBRATION_ENTER`
- publish UI message: `Calibrating workspace...`
- update health status
- log entry

### 8.3 `run(ctx)`

Responsibilities:

1. check camera service is available
2. read or access one valid current frame
3. load workspace config
4. validate workspace config
5. prepare workspace transformer
6. test-transform one frame
7. store workspace metadata
8. update health status
9. transition to `IDLE_NO_CARD`

Recommended internal substates:

```text
CALIBRATION_ENTER
CALIBRATION_LOAD_WORKSPACE_CONFIG
CALIBRATION_VALIDATE_WORKSPACE
CALIBRATION_CREATE_TRANSFORM
CALIBRATION_TEST_FRAME
CALIBRATION_READY
CALIBRATION_FAILED
```

### 8.4 `exit(ctx)`

Responsibilities:

- log state exit
- keep camera open
- keep workspace transformer stored in context
- publish UI message: `Workspace ready. Waiting for card.`

---

## 9. Workspace Service

Recommended file:

```text
app/services/workspace_service.py
```

Alternative:

```text
app/cv/workspace.py
```

### 9.1 Responsibilities

The workspace service should:

- parse workspace config
- validate workspace geometry
- create crop or homography transform
- apply transform to raw frames
- expose workspace metadata
- support normalized score mapping later

### 9.2 Minimal API

```python
class WorkspaceService:
    def configure(self, config: WorkspaceConfig) -> None:
        ...

    def validate(self, frame_shape: tuple[int, ...]) -> None:
        ...

    def transform(self, frame: np.ndarray) -> np.ndarray:
        ...

    def get_status(self) -> WorkspaceStatus:
        ...
```

### 9.3 Workspace Status

```python
@dataclass
class WorkspaceStatus:
    status: str
    mode: str
    width: int | None = None
    height: int | None = None
    score_axis: str = "x"
    invert_score_axis: bool = False
    last_error: str | None = None
```

Status values:

```text
NOT_INITIALIZED
VALIDATING
OK
ERROR
```

---

## 10. Health Status Requirements

During calibration:

```json
{
  "state": "CALIBRATION",
  "substate": "CALIBRATION_VALIDATE_WORKSPACE",
  "services": {
    "camera": {
      "status": "OK"
    },
    "workspace": {
      "status": "VALIDATING",
      "mode": "manual_rect"
    }
  }
}
```

After calibration success:

```json
{
  "state": "CALIBRATION",
  "substate": "CALIBRATION_READY",
  "services": {
    "workspace": {
      "status": "OK",
      "mode": "manual_rect",
      "width": 480,
      "height": 340,
      "score_axis": "x",
      "invert_score_axis": false
    }
  },
  "next_state": "IDLE_NO_CARD"
}
```

On calibration failure:

```json
{
  "state": "CALIBRATION",
  "substate": "CALIBRATION_FAILED",
  "services": {
    "workspace": {
      "status": "ERROR",
      "last_error": "Workspace rectangle is outside frame bounds"
    }
  },
  "next_state": "ERROR_SAFE"
}
```

---

## 11. UI Requirements During Calibration

The UI should show simple status messages:

```text
Calibrating workspace...
Workspace config loaded.
Workspace ready.
Waiting for card...
```

On failure:

```text
Workspace calibration failed.
Please check workspace configuration.
```

No full calibration editor is required in this sprint.

A debug overlay may be added later.

---

## 12. Card Detection MVP

### 12.1 Detection Strategy

Use classical OpenCV first.

Recommended pipeline:

```text
workspace_frame
  ↓
convert to grayscale
  ↓
blur
  ↓
threshold or edge detection
  ↓
morphological cleanup
  ↓
find contours
  ↓
filter contours by area
  ↓
fit minAreaRect
  ↓
filter by aspect ratio
  ↓
calculate confidence
  ↓
return best candidate
```

### 12.2 Why Classical CV?

The object is:

- flat
- rectangular
- on a planar table
- viewed from a top-down camera
- expected inside a known workspace

This is exactly the kind of problem where simple OpenCV should be tried before deep learning.

Deep learning can be considered later if the real booth environment is too variable.

---

## 13. Detector Service

Recommended file:

```text
app/cv/classical_card_detector.py
```

### 13.1 Responsibilities

The detector should:

- accept a workspace frame
- produce zero or more candidates
- choose the best candidate
- estimate pose-like metadata
- provide detector status/debug information

### 13.2 Minimal API

```python
class ClassicalCardDetector:
    def detect(self, workspace_frame: np.ndarray) -> CardDetectionResult:
        ...
```

### 13.3 Detection Result

```python
@dataclass
class CardDetectionResult:
    visible: bool
    candidate: CardPose | None = None
    candidates_count: int = 0
    status: str = "OK"
    debug: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
```

### 13.4 Card Pose

```python
@dataclass
class CardPose:
    visible: bool
    x: float
    y: float
    theta_deg: float
    width: float
    height: float
    confidence: float
    x_normalized: float | None = None
```

Coordinate convention:

```text
x, y, width, height are in workspace pixel coordinates.
theta_deg is the rectangle angle from OpenCV/minAreaRect.
x_normalized is mapped to 0.0 ... 1.0 along the configured score axis.
```

---

## 14. Detector Configuration

Recommended config:

```yaml
detector:
  type: "classical"
  enabled: true

  preprocessing:
    grayscale: true
    blur_kernel: 5
    threshold_mode: "adaptive"
    canny_enabled: false

  contour_filter:
    min_area_px: 1000
    max_area_ratio: 0.8
    min_aspect_ratio: 1.2
    max_aspect_ratio: 2.2

  confidence:
    min_confidence: 0.5

  candidate:
    required_stable_frames: 3
```

Notes:

- Business cards are often around an aspect ratio of `1.75`, but real cards vary.
- Keep thresholds configurable.
- Start tolerant, then tighten after observing real camera frames.
- Do not overfit to one test card too early.

---

## 15. Score Axis and Normalization

For `score_axis: "x"`:

```text
x_normalized = clamp(center_x / workspace_width, 0.0, 1.0)
```

If inverted:

```text
x_normalized = 1.0 - x_normalized
```

Clamp function:

```python
def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
```

Optional later rating mapping:

```text
rating = 1 + round(x_normalized * 9)
```

Do not make final rating display central in this sprint.  
The first goal is reliable detection.

---

## 16. Updated `IDLE_NO_CARD` Responsibilities

After this sprint, `IDLE_NO_CARD` should:

- read camera frames continuously or at a configured interval
- apply workspace transform
- run card detector
- update detector health
- publish UI status
- stay in `IDLE_NO_CARD` if no card is visible
- transition to `CANDIDATE_DETECTED` if a plausible card appears

Recommended loop:

```text
while state == IDLE_NO_CARD:
  read frame
  if frame invalid:
      transition to RECOVERY

  workspace_frame = workspace.transform(frame)
  result = detector.detect(workspace_frame)

  if result.visible:
      store candidate
      transition to CANDIDATE_DETECTED

  sleep(idle_poll_interval_s)
```

Health during idle:

```json
{
  "state": "IDLE_NO_CARD",
  "substate": "IDLE_WAITING_FOR_CARD",
  "services": {
    "camera": {
      "status": "OK",
      "frames_read": 132
    },
    "workspace": {
      "status": "OK"
    },
    "detector": {
      "status": "OK",
      "visible": false,
      "candidates_count": 0
    }
  }
}
```

---

## 17. `CANDIDATE_DETECTED` State

### 17.1 Purpose

`CANDIDATE_DETECTED` is a debounce/hysteresis state.

It prevents the system from entering `TRACKING` because of one noisy frame.

### 17.2 Responsibilities

- continue reading frames
- continue workspace transform
- continue detection
- require candidate to be visible for `N` consecutive frames
- if stable: transition to `TRACKING`
- if lost: transition back to `IDLE_NO_CARD`

Recommended config:

```yaml
tracking:
  candidate_required_frames: 3
  candidate_max_lost_frames: 2
```

For the first implementation, it is acceptable to transition after one valid candidate if the state exists and can be extended later.

---

## 18. Minimal `TRACKING` Stub

Full tracking is not required in this sprint.

A minimal `TRACKING` state may:

- receive latest `CardPose`
- publish `x_normalized`
- update UI score
- transition back to `IDLE_NO_CARD` if card is lost

Advanced smoothing belongs to a later sprint.

---

## 19. Recommended Module Structure

Add or update:

```text
app/
├── states/
│   ├── calibration.py
│   ├── idle.py
│   ├── candidate_detected.py
│   └── tracking.py              # optional minimal stub
│
├── services/
│   └── workspace_service.py
│
├── cv/
│   ├── classical_card_detector.py
│   ├── card_pose.py
│   └── score_mapper.py          # optional/minimal
```

Keep it pragmatic.

Do not create five micro-files for something that fits clearly into one module.  
This is a demo, not a cathedral with imports.

---

## 20. Configuration Requirements

Recommended config additions:

```yaml
workspace:
  mode: "manual_rect"
  source_frame: "camera"
  rect_px:
    x: 80
    y: 60
    width: 480
    height: 340
  score_axis: "x"
  invert_score_axis: false

detector:
  type: "classical"
  enabled: true

  preprocessing:
    grayscale: true
    blur_kernel: 5
    threshold_mode: "adaptive"
    canny_enabled: false

  contour_filter:
    min_area_px: 1000
    max_area_ratio: 0.8
    min_aspect_ratio: 1.2
    max_aspect_ratio: 2.2

  confidence:
    min_confidence: 0.5

tracking:
  candidate_required_frames: 3
  candidate_max_lost_frames: 2
```

---

## 21. Error Handling

### 21.1 Calibration Errors

Transition to `ERROR_SAFE` if:

```text
workspace config missing
workspace mode unsupported
manual_rect outside frame bounds
manual_quad has invalid points
output_size invalid
score_axis unsupported
```

Transition to `RECOVERY` if:

```text
camera frame unavailable during calibration
camera service not ready
```

### 21.2 Detection Errors

Detection should usually not crash the app.

If detection fails for one frame:

```text
log warning
detector.status = DEGRADED or ERROR
stay in IDLE_NO_CARD if possible
```

If repeated frame/camera failure occurs:

```text
IDLE_NO_CARD → RECOVERY
```

If detector config is invalid:

```text
CALIBRATION or IDLE_NO_CARD → ERROR_SAFE
```

---

## 22. Logging Requirements

Calibration logs:

```text
[CALIBRATION] Entering CALIBRATION state
[CALIBRATION] Loading workspace config
[CALIBRATION] Workspace mode=manual_rect
[CALIBRATION] Validating workspace against frame shape=(480, 640, 3)
[CALIBRATION] Workspace ready width=<w> height=<h>
[CALIBRATION] Transitioning to IDLE_NO_CARD
```

Detection logs:

```text
[DETECTOR] First card candidate detected confidence=<c>
[DETECTOR] Candidate lost
[DETECTOR] Detection error: <error>
```

Do not log every frame at INFO level.  
Use DEBUG for per-frame details.

---

## 23. UI Requirements

The UI should show:

```text
Calibrating workspace...
Workspace ready.
Waiting for card...
Card candidate detected.
Tracking card...
```

During `IDLE_NO_CARD`, the UI should look alive, not broken.

Minimum visible UI:

```text
CV Card Demo
Waiting for card...
```

When a card is detected:

```text
Card detected
Score: <x_normalized>
```

The live ranking bar may be updated minimally if `x_normalized` is already available.

---

## 24. Debug Requirements

Minimal debug data should be available through health or a debug endpoint:

```json
{
  "workspace": {
    "status": "OK",
    "mode": "manual_rect",
    "width": 480,
    "height": 340
  },
  "detector": {
    "status": "OK",
    "visible": true,
    "candidates_count": 1,
    "confidence": 0.82,
    "x_normalized": 0.43
  }
}
```

Optional later debug overlay:

- raw frame
- workspace rectangle
- warped workspace frame
- binary mask
- detected contour
- rotated rectangle
- center point

Do not block the MVP on the overlay.

---

## 25. Manual Test Plan

### Test 1: Calibration State Reached

Command:

```bash
source venv/bin/activate
python -m app.main --config config/config.yaml --initial-state BOOT
```

Expected result:

```text
BOOT → INIT_CAM → CALIBRATION → IDLE_NO_CARD
```

Status:

```text
NOT_RUN
```

---

### Test 2: Health Shows Workspace

Command:

```bash
curl http://localhost:8000/api/health
```

Expected result:

```json
{
  "services": {
    "workspace": {
      "status": "OK"
    }
  }
}
```

Status:

```text
NOT_RUN
```

---

### Test 3: Invalid Workspace Config

Config example:

```yaml
workspace:
  mode: "manual_rect"
  rect_px:
    x: 99999
    y: 99999
    width: 480
    height: 340
```

Expected result:

```text
CALIBRATION fails
state transitions to ERROR_SAFE
health shows workspace.status=ERROR
UI shows workspace calibration failed
```

Status:

```text
NOT_RUN
```

---

### Test 4: No Card in Workspace

Expected result:

```text
state remains IDLE_NO_CARD
detector.visible=false
candidates_count=0
UI shows "Waiting for card"
```

Status:

```text
NOT_RUN
```

---

### Test 5: Card in Workspace

Place a business card or similar rectangular card inside the workspace.

Expected result:

```text
detector.visible=true
candidate contains x, y, theta, width, height, confidence
x_normalized is between 0.0 and 1.0
state transitions to CANDIDATE_DETECTED
```

Status:

```text
NOT_RUN
```

---

### Test 6: Move Card Horizontally

Move the card left to right inside the workspace.

Expected result:

```text
x_normalized changes from low to high
no crashes
UI/health show updated candidate data
```

Status:

```text
NOT_RUN
```

---

## 26. Acceptance Criteria

This sprint is complete when:

- [ ] `CALIBRATION` state exists
- [ ] `INIT_CAM` transitions to `CALIBRATION` instead of directly to `IDLE_NO_CARD`
- [ ] workspace config is loaded
- [ ] workspace config is validated
- [ ] workspace frame can be produced from camera frame
- [ ] workspace status is visible in health endpoint
- [ ] `IDLE_NO_CARD` runs a frame/detection loop
- [ ] classical detector exists
- [ ] detector can return `visible=false` with no card
- [ ] detector can return `visible=true` with a card
- [ ] `CardPose` contains `x`, `y`, `theta_deg`, `width`, `height`, `confidence`
- [ ] `x_normalized` is calculated in range `0.0 ... 1.0`
- [ ] candidate detection causes transition to `CANDIDATE_DETECTED`
- [ ] invalid workspace config is handled visibly
- [ ] no WLED dependency is introduced
- [ ] manual tests are documented
- [ ] errors are documented in `errors_and_fixes.md`
- [ ] global checklist is updated

---

## 27. Documentation Updates Required

Create or update:

```text
docs/sub-sprint-phase/03_workspace_calibration/checklist.md
docs/sub-sprint-phase/03_workspace_calibration/errors_and_fixes.md

docs/sub-sprint-phase/04_card_detection/checklist.md
docs/sub-sprint-phase/04_card_detection/errors_and_fixes.md

docs/global_checklist.md
```

Recommended global checklist changes:

```text
03 Workspace Calibration → IN_PROGRESS
04 Card Detection → IN_PROGRESS
```

When complete:

```text
03 Workspace Calibration → DONE
04 Card Detection → DONE
```

---

## 28. Known Risks

### 28.1 Lighting

Bad lighting can break threshold-based detection.

Mitigation:

- use diffuse lighting
- avoid glossy table surfaces
- keep camera exposure stable
- keep workspace background controlled

### 28.2 Card Similar to Table Color

If the card has low contrast against the table, simple thresholding may fail.

Mitigation:

- use edge detection
- use adaptive thresholding
- use color/background difference if needed
- improve table background

### 28.3 Hands in Workspace

A hand may be detected as a contour.

Mitigation:

- filter by rectangle shape
- filter by aspect ratio
- require stable candidate for several frames
- ignore extremely large contours

### 28.4 Shadows

Shadows may generate contours.

Mitigation:

- blur and morphology
- adaptive threshold
- better lighting
- tune contour filters

### 28.5 Perspective / Camera Angle

If the camera is not truly top-down, a simple rectangular crop may be insufficient.

Mitigation:

- use `manual_quad` and perspective transform
- add ArUco calibration later if needed

---

## 29. Recommended Implementation Order

1. Add `workspace`, `detector`, and `tracking` config sections.
2. Add `WorkspaceService` with `manual_rect`.
3. Add `CALIBRATION` state.
4. Change state flow from `INIT_CAM → IDLE_NO_CARD` to `INIT_CAM → CALIBRATION → IDLE_NO_CARD`.
5. Add `ClassicalCardDetector`.
6. Update `IDLE_NO_CARD` to read frames, transform workspace, and run detection.
7. Add minimal `CANDIDATE_DETECTED`.
8. Add health fields for workspace and detector.
9. Test no-card and card scenarios.
10. Update phase checklists and errors.

---

## 30. Final Summary

This sprint should make the application see its working area and detect a card inside it.

The intended result:

```text
BOOT
  ↓
INIT_CAM
  ↓
CALIBRATION
  ↓
IDLE_NO_CARD
  ↓
CANDIDATE_DETECTED
```

The system should remain simple:

```text
manual workspace config
classical OpenCV detector
health-visible state
no WLED dependency
no deep learning
```

The sprint is successful when the application can reliably answer:

```text
Is there a plausible card in the workspace?
Where is its center?
What is its horizontal normalized position?
```

Stable first. Fancy later.
