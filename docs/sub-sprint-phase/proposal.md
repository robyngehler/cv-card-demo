# Proposal: Robust Card Detection and Tracking under Hand Interference

**Project:** CV-Card-Demo  
**Phase:** 04 Card Detection / 06 Tracking Stability  
**Date:** 2026-06-05  
**Status:** Proposal for next implementation sprint

---

## 1. Executive Summary

The current card detection pipeline works for clearly visible business cards on the workspace, but it becomes unstable when a user's hand enters the frame, touches the card, or partially occludes it.

The observed issue is not that card detection is fundamentally broken. The actual problem is that the system currently behaves too much like a frame-by-frame detector and not enough like a tracker. As soon as the card contour becomes fragmented by hand occlusion, shadows, skin texture, or motion blur, the detector loses confidence and the state machine risks falling back to `IDLE_NO_CARD`.

This creates poor user feedback: while the user is actively moving the card, the UI may lose the card exactly when feedback is most important.

The proposed solution is to separate the responsibilities of detection and tracking:

```text
Detector:
  Finds the card when it is clearly visible.

Tracker:
  Keeps the card alive across short occlusions, hand movement, and temporary detector failures.
```

The live tracking must not be sacrificed. During hand interaction, the system should continue publishing a stable score based on the last known or predicted card position.

---

## 2. Current Implementation Assessment

### 2.1 What already works

The current implementation has several good design choices:

1. **Classical OpenCV pipeline**  
   The current approach is simple, fast, inspectable, and suitable for a Jetson-based booth demo.

2. **Workspace transformation before detection**  
   Detection runs on a defined workspace area instead of the full camera frame. This reduces noise and keeps scoring consistent.

3. **OTSU thresholding for the current setup**  
   The switch from adaptive thresholding to OTSU was correct for the high-contrast setup with a dark workspace and light cards. Adaptive thresholding produced edge rings and caused the workspace border to dominate. OTSU produced cleaner solid card regions.

4. **Aspect-ratio filtering**  
   Business cards have a predictable rectangular aspect ratio. Filtering candidates by aspect ratio is an effective and cheap way to reject workspace borders, shadows, and unrelated contours.

5. **Temporal debouncing already introduced**  
   The existing `candidate_required_frames` and `candidate_max_lost_frames` approach is an important first step toward robust tracking.

### 2.2 Current limitation

The current pipeline still behaves too much like this:

```text
Frame → Threshold → Contours → minAreaRect → Confidence → visible true/false
```

This means each frame can independently decide whether the card exists. That is fragile.

When a hand partially occludes the card, the card may no longer appear as one clean closed contour. Instead, it can split into multiple smaller regions. The detector then sees fragments instead of the full card and rejects them because area, aspect ratio, or confidence no longer pass the thresholds.

The current temporal smoothing helps with very brief losses, but a hand moving a card can easily occlude the card for longer than two frames. At 20-30 FPS, two frames correspond to only about 67-100 ms. That is too short for real user interaction.

---

## 3. Problem Statement

### 3.1 Observed behavior

Typical sequence:

```text
Frame N:
  Card visible
  Confidence around 0.39
  Detection accepted

Frame N+1:
  Hand touches or occludes card
  Card contour fragments
  Confidence may drop to around 0.15
  Detection rejected

Frame N+2:
  Hand still present or moving card
  Detection still unstable
  UI risks losing card feedback

Frame N+k:
  Hand removed
  Card contour reforms
  Detection resumes
```

### 3.2 User experience impact

This behavior is unacceptable for the demo because the user's hand is naturally present when moving the card. The system must continue giving live feedback during this interaction.

The ranking bar or score output should not disappear just because the card is briefly partially covered.

### 3.3 Technical root causes

1. **Contour fragmentation**  
   Hand occlusion breaks the card into smaller visible regions.

2. **Low baseline confidence margin**  
   The baseline confidence is only slightly above the minimum threshold, so even small disturbances can cause rejection.

3. **Area score calibration**  
   The confidence formula currently penalizes small objects too heavily because the card occupies only a small percentage of the workspace frame.

4. **Single-frame decision behavior**  
   The detector has insufficient memory of previous detections.

5. **Frame-count based loss tolerance is too short**  
   A tolerance of two frames is useful for noise, but insufficient for realistic hand movement.

---

## 4. Proposed Architecture

The next version should use a tracking-by-detection architecture.

```text
Camera Frame
    ↓
Workspace Transform
    ↓
Detector
    ↓
Candidate Selection
    ↓
Card Tracker
    ↓
Score Publisher
    ↓
UI / WebSocket / Optional WLED
```

The detector remains responsible for finding possible card candidates. The tracker is responsible for continuity, prediction, and temporary occlusion handling.

---

## 5. Proposed State Behavior

### 5.1 IDLE_NO_CARD

Purpose:

- Wait for a clear card candidate.
- Avoid false positives.

Behavior:

```text
If detector finds valid card:
  transition to CANDIDATE_DETECTED
else:
  remain in IDLE_NO_CARD
```

---

### 5.2 CANDIDATE_DETECTED

Purpose:

- Confirm that the detected card is stable before entering active tracking.

Behavior:

```text
If card detected:
  increment stable_frame_count
  reset lost_frame_count

If card temporarily lost:
  increment lost_frame_count
  remain in CANDIDATE_DETECTED while within tolerance

If stable_frame_count >= candidate_required_frames:
  initialize tracker
  transition to TRACKING

If lost_frame_count exceeds candidate_max_lost_frames:
  transition to IDLE_NO_CARD
```

Recommended configuration:

```yaml
tracking:
  candidate_required_frames: 3
  candidate_max_lost_frames: 2
```

This state can remain frame-count based because it is only responsible for initial confirmation.

---

### 5.3 TRACKING

Purpose:

- Continue tracking the selected card while the user moves it.
- Keep UI feedback alive during short hand occlusions.
- Publish score continuously.

Behavior:

```text
If detector finds a matching card:
  update tracker with current detection
  publish score with source = "detected"
  reset lost timer

If detector fails but tracker is still recent:
  predict current card position
  publish score with source = "tracked_occluded"
  remain in TRACKING

If detector fails for too long:
  publish lost state
  transition to IDLE_NO_CARD
```

Recommended configuration:

```yaml
tracking:
  tracking_max_lost_duration_s: 0.5
  tracking_prediction_enabled: true
  tracking_match_max_distance_px: 80
```

The key change is to use a time-based loss tolerance in `TRACKING`, not only a frame-based one.

---

## 6. Card Tracker Design

### 6.1 Tracker state

The tracker should store:

```python
last_center: tuple[float, float]
last_size: tuple[float, float]
last_angle: float
last_x_norm: float
last_confidence: float
velocity: tuple[float, float]
last_seen_time: float
tracking_source: str
```

### 6.2 Update logic

When a valid detection is available:

```python
dt = now - last_seen_time
velocity = (current_center - last_center) / dt
last_center = current_center
last_size = current_size
last_angle = current_angle
last_x_norm = current_x_norm
last_confidence = current_confidence
last_seen_time = now
tracking_source = "detected"
```

### 6.3 Prediction logic

When detection is temporarily lost:

```python
predicted_center = last_center + velocity * dt
predicted_x_norm = center_to_x_norm(predicted_center)
tracking_source = "tracked_occluded"
```

The prediction should be clamped to the workspace bounds:

```python
predicted_x_norm = clamp(predicted_x_norm, 0.0, 1.0)
```

### 6.4 Candidate matching

When multiple candidates exist, the tracker should prefer the candidate nearest to the predicted card position.

```python
if distance(candidate.center, predicted_center) < tracking_match_max_distance_px:
    accept candidate as tracked card
```

This avoids jumping to another card or a random rectangular object.

---

## 7. Score Publishing Contract

The UI should receive not only the score, but also the tracking source.

Proposed payload:

```json
{
  "visible": true,
  "score": 0.43,
  "x_norm": 0.43,
  "confidence": 0.39,
  "state": "TRACKING",
  "source": "detected"
}
```

During short occlusion:

```json
{
  "visible": true,
  "score": 0.44,
  "x_norm": 0.44,
  "confidence": 0.15,
  "state": "TRACKING",
  "source": "tracked_occluded"
}
```

After real loss:

```json
{
  "visible": false,
  "score": null,
  "x_norm": null,
  "confidence": 0.0,
  "state": "IDLE_NO_CARD",
  "source": "lost"
}
```

The UI can optionally dim the score indicator during `tracked_occluded`, but it must not remove feedback immediately.

---

## 8. Detector Improvements

### 8.1 Confidence formula

The current confidence formula appears too dependent on area relative to the entire workspace. Since cards are naturally small, this gives a low baseline confidence.

Current approximate behavior:

```python
confidence = 0.6 * area_score + 0.4 * aspect_score
```

Proposed behavior:

```python
area_score = clamp(area / expected_card_area_px, 0.0, 1.0)
aspect_score = 1.0 - abs(aspect - target_aspect) / aspect_tolerance
rectangularity_score = contour_area / min_area_rect_area

confidence = (
    0.35 * area_score +
    0.35 * aspect_score +
    0.30 * rectangularity_score
)
```

Recommended config additions:

```yaml
detector:
  confidence:
    expected_card_area_px: 3200
    target_aspect_ratio: 1.65
    aspect_tolerance: 0.55
    weight_area: 0.35
    weight_aspect: 0.35
    weight_rectangularity: 0.30
```

### 8.2 Rectangularity score

Rectangularity measures how well the contour fills its rotated bounding box.

```python
rectangularity = contour_area / (rect_width * rect_height)
```

A real card should usually have higher rectangularity than hand fragments, shadows, or border artifacts.

### 8.3 Morphological cleanup

The threshold mask should be tested with light morphological cleanup:

```python
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
```

This should be evaluated carefully. Too much closing can merge the card with the hand, which would make the problem worse in a very creative and deeply annoying way.

Recommended config:

```yaml
detector:
  preprocessing:
    morphology_enabled: true
    morphology_kernel_size: 5
    morphology_close_iterations: 1
    morphology_open_iterations: 1
```

---

## 9. Optional Hand Tracking

Hand tracking can be useful, but it should not be the first implementation step.

Possible use cases:

1. Detect whether a hand is currently occluding the card.
2. Increase tracking tolerance while a hand is present.
3. Ignore contours inside the hand bounding box.
4. Mark UI state as `hand_occlusion`.

However, hand tracking introduces additional dependencies and runtime cost. It should be considered optional after the tracker is implemented.

Recommended later approach:

```text
If hand detected near last card position:
  allow longer occlusion hold
  keep publishing predicted card score
else:
  use normal lost timeout
```

This should be treated as an enhancement, not a replacement for card tracking.

---

## 10. Implementation Plan

### Sprint 1: Tracking continuity

Goal:

- Prevent UI flicker during realistic hand interaction.

Tasks:

- [ ] Add `tracking_max_lost_duration_s` to config.
- [ ] Add `tracking_match_max_distance_px` to config.
- [ ] Implement `CardTracker` helper class.
- [ ] Store last known card position, size, angle, confidence, and velocity.
- [ ] Update `TRACKING` state to use tracker prediction during lost frames.
- [ ] Publish `source = detected | tracked_occluded | lost`.
- [ ] Keep UI score alive during short occlusion.

Acceptance criteria:

- [ ] A short hand occlusion does not transition to `IDLE_NO_CARD`.
- [ ] UI score remains visible during hand interaction.
- [ ] Tracking returns to normal once the card is visible again.
- [ ] Card removal still transitions to `IDLE_NO_CARD` after timeout.

---

### Sprint 2: Detector confidence recalibration

Goal:

- Increase baseline confidence without increasing false positives too much.

Tasks:

- [ ] Add rectangularity calculation.
- [ ] Replace frame-relative area scoring with expected-card-area scoring.
- [ ] Add debug output for area, aspect, rectangularity, and final confidence.
- [ ] Tune `expected_card_area_px` using real camera data.
- [ ] Compare old and new scoring on saved debug frames.

Acceptance criteria:

- [ ] Clean visible card confidence is comfortably above threshold.
- [ ] Hand fragments are still rejected unless matched by tracker.
- [ ] Workspace border remains rejected.
- [ ] Multiple cards are handled consistently.

---

### Sprint 3: Mask cleanup and regression tests

Goal:

- Improve mask stability and make future tuning measurable.

Tasks:

- [ ] Add optional morphology config.
- [ ] Save debug frames for raw frame, threshold mask, morphology result, contours, and selected candidate.
- [ ] Create test image sequence with hand occlusion.
- [ ] Add regression script for saved frames.
- [ ] Record metrics per frame.

Acceptance criteria:

- [ ] Debug output clearly explains why a candidate was accepted or rejected.
- [ ] Regression test can reproduce the hand occlusion scenario.
- [ ] Parameter changes can be evaluated quantitatively.

---

### Sprint 4: Optional hand-awareness

Goal:

- Improve occlusion classification and user feedback.

Tasks:

- [ ] Evaluate hand landmark detection performance on Jetson.
- [ ] Detect hand bounding box near last known card position.
- [ ] Extend tracking hold when hand is present.
- [ ] Publish `source = hand_occluded` if useful.

Acceptance criteria:

- [ ] Hand detection does not reduce FPS below acceptable limits.
- [ ] Card tracking remains stable when the hand is visible.
- [ ] No new dependency blocks the MVP.

---

## 11. Recommended Configuration Draft

```yaml
tracking:
  candidate_required_frames: 3
  candidate_max_lost_frames: 2

  tracking_max_lost_duration_s: 0.5
  tracking_prediction_enabled: true
  tracking_match_max_distance_px: 80
  tracking_velocity_smoothing_alpha: 0.6

  publish_last_position_during_occlusion: true


detector:
  confidence:
    min_confidence: 0.35
    expected_card_area_px: 3200
    target_aspect_ratio: 1.65
    aspect_tolerance: 0.55
    weight_area: 0.35
    weight_aspect: 0.35
    weight_rectangularity: 0.30

  preprocessing:
    threshold_mode: "otsu"
    morphology_enabled: true
    morphology_kernel_size: 5
    morphology_close_iterations: 1
    morphology_open_iterations: 1
```

---

## 12. Testing Plan

### Test 1: Static card

Expected result:

```text
state = TRACKING
source = detected
confidence >= min_confidence
score updates normally
```

### Test 2: Short hand pass over card

Expected result:

```text
state remains TRACKING
source switches detected → tracked_occluded → detected
UI does not flicker
score remains visible
```

### Test 3: Hand slides card

Expected result:

```text
state remains TRACKING
score follows the card movement approximately
no immediate fallback to IDLE_NO_CARD
```

### Test 4: Card removed

Expected result:

```text
state transitions to IDLE_NO_CARD after tracking_max_lost_duration_s
UI cleanly shows no card
```

### Test 5: Multiple cards in workspace

Expected result:

```text
tracker remains locked to the originally tracked card
candidate matching uses proximity to predicted position
system does not jump randomly to another card
```

---

## 13. Debug Metrics to Log

Each processed frame should optionally log:

```text
timestamp
state
tracking_source
candidate_count
best_confidence
best_area
best_aspect
best_rectangularity
x_norm
lost_duration_s
tracker_center
predicted_center
transition_decision
```

This makes tuning measurable instead of turning the config file into a shrine of desperate guesses.

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Tracker keeps card alive after it was removed | UI may show stale score | Use strict max lost duration, e.g. 0.5-1.0 s |
| Tracker jumps to another card | Wrong score | Match candidates by distance to predicted position |
| Morphology merges hand and card | Worse contour quality | Keep morphology optional and debug visually |
| Lower confidence threshold causes false positives | Wrong detection | Improve scoring instead of simply lowering threshold |
| Hand tracking adds too much complexity | Delays MVP | Keep hand tracking optional |

---

## 15. Final Recommendation

The next implementation step should not be another attempt to make every frame perfectly detect the card. That will remain fragile under real hand interaction.

The correct next step is:

```text
Implement proper TRACKING continuity with last-known position, velocity prediction,
time-based occlusion tolerance, and source-aware score publishing.
```

In short:

```text
Detect when the card is visible.
Track when reality becomes rude.
```

This protects the most important requirement: the user must continue receiving live feedback while moving the card, even when a hand is in the frame.
