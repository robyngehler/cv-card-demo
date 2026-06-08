# Frame Scaling and Workspace Coordinate Fix

## Problem

The CV card demo uses two different image resolutions at the same time:

- **Full camera frame:** `3840x2160` for high-resolution snapshots and OCR crops.
- **Live processing frame:** `1920x1080` for faster card detection, hand tracking, and UI/debug processing.

After switching the camera to 4K while keeping the workspace configuration based on `1920x1080`, card detection became unstable. The system briefly detected a business-card candidate in `IDLE_NO_CARD`, but then lost it during `CANDIDATE_DETECTED` before reaching `TRACKING`.

The log showed this pattern:

```text
Business-card candidate detected confidence=0.81 x_normalized=0.70
CANDIDATE_DETECTED: Card lost for 3 frames
```

This indicates that the detector can see the card initially, but the coordinate handling is inconsistent between states.

## Root Cause

The workspace coordinates in `config.yaml` are defined for the live processing frame, e.g. `1920x1080`.

However, not all states necessarily use the same frame size before calling the detector:

- `TRACKING` already reads a full 4K frame and downsizes it to the live processing frame before detection.
- `IDLE_NO_CARD` and `CANDIDATE_DETECTED` may still read and process the full 4K frame directly.

This creates a coordinate-space mismatch:

```text
Workspace config:       1920x1080 coordinates
Detector input frame:   possibly 3840x2160
Result:                 workspace is applied at the wrong scale
```

As a result, the detector may search in the wrong region or use an incorrectly scaled workspace. The card appears unstable or disappears, even though the camera and detector are technically working.

## Intended Architecture

All live detection states should use the same processing frame size:

```text
Camera reads full 4K frame
        ↓
Frame is resized to 1920x1080 for live processing
        ↓
Card detection, hand tracking, fusion, and workspace logic run on 1920x1080
        ↓
The original full 4K frame is kept for snapshots and OCR crops
        ↓
Crop coordinates are scaled from live-frame space back to full-frame space
```

## Solution

Create one shared helper function for frame scaling and use it consistently in all states that call the detector.

### 1. Add a shared frame-scaling helper

Create:

```text
app/utils/frame_scaling.py
```

```python
import cv2


def make_live_frame(full_frame, config):
    camera_config = config.get("camera", {})
    live_config = camera_config.get("live_processing", {})

    if not live_config.get("enabled", False):
        return full_frame, 1.0, 1.0

    live_width = int(live_config.get("width", full_frame.shape[1]))
    live_height = int(live_config.get("height", full_frame.shape[0]))

    if full_frame.shape[1] == live_width and full_frame.shape[0] == live_height:
        return full_frame, 1.0, 1.0

    live_frame = cv2.resize(
        full_frame,
        (live_width, live_height),
        interpolation=cv2.INTER_AREA,
    )

    scale_x = full_frame.shape[1] / float(live_width)
    scale_y = full_frame.shape[0] / float(live_height)

    return live_frame, scale_x, scale_y
```

### 2. Use the helper in every detector state

The following states should all follow the same pattern:

- `IDLE_NO_CARD`
- `CANDIDATE_DETECTED`
- `TRACKING`

Before detector execution:

```python
from app.utils.frame_scaling import make_live_frame
```

Then replace direct detector input from the raw camera frame with:

```python
full_frame = camera.read_frame(timeout_s=0.5)
frame, scale_x, scale_y = make_live_frame(full_frame, self.context.config)

self.context.runtime["last_frame"] = full_frame
self.context.runtime["last_live_frame"] = frame
self.context.runtime["live_to_full_scale"] = {
    "x": scale_x,
    "y": scale_y,
}

result = detector.detect(frame, state_name=self.name)
```

Important rule:

```text
Detector input = live frame
Snapshot input = full frame
```

### 3. Keep workspace config in live-frame coordinates

The workspace values in `config.yaml` should stay based on `1920x1080`, not `3840x2160`.

Example:

```yaml
camera:
  width: 3840
  height: 2160
  live_processing:
    enabled: true
    width: 1920
    height: 1080

workspace:
  card:
    mode: "manual_rect"
    source_frame: "live"
    rect_px:
      x: 390
      y: 330
      width: 1180
      height: 635
```

Do not scale these workspace values to 4K manually. The code should handle scaling when needed.

### 4. Snapshot crop scaling

Snapshots should save the full 4K frame. Crop coordinates should be calculated in live-frame space and then scaled back to full-frame space using:

```python
scale = self.context.runtime.get("live_to_full_scale", {"x": 1.0, "y": 1.0})
scale_x = float(scale.get("x", 1.0))
scale_y = float(scale.get("y", 1.0))
```

This ensures that OCR receives a high-resolution crop while detection remains fast.

## Temporary Debug Settings

To verify the fix, the candidate stability thresholds can be relaxed temporarily:

```yaml
tracking:
  candidate_required_frames: 2
  candidate_max_lost_frames: 5
```

Once detection is stable again, use stricter values such as:

```yaml
tracking:
  candidate_required_frames: 3
  candidate_max_lost_frames: 4
```

## Expected Result

After applying the fix:

- The camera still runs at `3840x2160`.
- Detection runs consistently on `1920x1080` in all states.
- The same workspace coordinates are valid in `IDLE_NO_CARD`, `CANDIDATE_DETECTED`, and `TRACKING`.
- The system should no longer detect a card briefly and then lose it immediately because of coordinate mismatch.
- Snapshots and OCR crops continue to use the full-resolution image.

## Files to Check

The most relevant files are:

```text
app/states/idle.py
app/states/candidate_detected.py
app/states/tracking.py
app/services/snapshot_service.py
app/services/workspace_service.py
config/config.yaml
```

The highest-priority fix is to make sure `idle.py` and `candidate_detected.py` use the same live-frame scaling logic as `tracking.py` before calling the detector.
