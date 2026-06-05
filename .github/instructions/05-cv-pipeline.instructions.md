---
applyTo: "app/cv/**/*.py"
---

# CV Pipeline Instructions

## Goal

Detect a flat card on a table from a top-down RGB camera and estimate its simplified 2D pose.

## Preferred MVP Approach

Use classical OpenCV first.

Recommended pipeline:

```text
frame
  ↓
crop workspace ROI
  ↓
optional perspective correction
  ↓
preprocessing
  ↓
threshold / edge / contour detection
  ↓
filter contours
  ↓
fit rotated rectangle
  ↓
estimate card center and angle
  ↓
map horizontal position to score
```

## Avoid Deep Learning Initially

Do not add YOLO, SAM, or any training pipeline unless explicitly requested.

Classical CV is preferred because:

- the object is planar
- the camera is top-down
- the workspace can be controlled
- latency should be low
- debugging must be easy
- this is a demo

## Card Candidate

Represent detections with structured data.

Example:

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

## Score Mapping

Map the horizontal table coordinate to:

```text
score = clamp((x - x_min) / (x_max - x_min), 0.0, 1.0)
```

Then optionally map to a 1-10 rating:

```text
rating = 1 + round(score * 9)
```

## Robustness

Use:

- area filtering
- aspect ratio filtering
- confidence score
- temporal smoothing
- lost-card timeout
- hysteresis for visible/not visible

## Performance Target

Aim for:

```text
20-30 Hz effective tracking update rate
```

Do not optimize before the simple implementation works.

## Debug Output

Support debug overlays eventually:

- card contour
- rotated rectangle
- center point
- score
- FPS
- confidence
- state
