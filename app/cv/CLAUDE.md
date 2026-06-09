# CV Pipeline — `app/cv/`

*Applies to all code under `app/cv/`. Loaded automatically here.*

## Goal

Detect a flat card on a table from a top-down RGB camera, track it with
continuity, and optionally fuse with hand-presence detection to guard snapshot
quality.

## Actual Modules

```text
app/cv/
├── classical_card_detector.py   — contour/threshold based card detection
├── yolo_card_detector.py        — YOLOv8-based card detection (optional)
├── card_tracker.py              — temporal tracking with continuity logic
├── fusion_tracker.py            — fuses card track + hand presence signal
└── hand_tracking.py             — MediaPipe hand detection wrapper
```

## Detection Strategy

Two detectors exist; `config.yaml → detector.type` selects which is active:

- `classical` — OpenCV contour + threshold pipeline. Preferred for low latency
  and easy debugging. Good for controlled lighting and background.
- `yolo` — YOLOv8n (`models/yolov8n.pt`). More robust under harder conditions.
  Adds ~50 ms startup, requires the model file.

```text
frame
  ↓
crop workspace ROI       (WorkspaceService defines ROI)
  ↓
detector (classical or yolo)
  ↓
CardDetection { visible, bbox, center, confidence }
  ↓
card_tracker.py          (temporal smoothing, continuity, lost-hold timeout)
  ↓
fusion_tracker.py        (suppress snapshot if hand present)
  ↓
score mapper             (x-position → 0.0 … 1.0)
```

## Card Candidate

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
```

## Hand Tracking

`hand_tracking.py` wraps MediaPipe Hands. Used exclusively to suppress false
snapshots when the visitor's hand is in the workspace. It does not affect card
position calculation.

## Fusion Tracker

`fusion_tracker.py` combines card track + hand presence:
- hand present → block SNAPSHOT transition (guard quality)
- hand absent + card stable → allow transition to SNAPSHOT

## Score Mapping

```text
score = clamp((x - x_min) / (x_max - x_min), 0.0, 1.0)
rating = 1 + round(score * 9)    # optional 1-10 scale
```

## Robustness

Use: area filtering, aspect-ratio filtering, confidence score, temporal
smoothing, lost-card timeout, hysteresis for visible/not-visible.

## Performance Target

```text
20-30 Hz effective tracking update rate
```

## Debug Output

Debug overlays supported: card contour, rotated rectangle, center point, score,
FPS, confidence, state. Controlled via `config.yaml → detector.debug_*`.
