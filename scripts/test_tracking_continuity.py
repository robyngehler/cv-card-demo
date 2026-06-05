#!/usr/bin/env python3

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.app_context import create_app_context
from app.config_loader import load_config
from app.cv.card_tracker import CardTracker
from app.cv.classical_card_detector import CardPose, ClassicalCardDetector


def make_pose(x: float, y: float, confidence: float = 0.9) -> CardPose:
    return CardPose(
        visible=True,
        x=x,
        y=y,
        theta_deg=0.0,
        width=160.0,
        height=95.0,
        confidence=confidence,
        x_normalized=x / 490.0,
    )


def test_detector_scoring() -> None:
    import cv2
    import numpy as np

    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)
    detector = ClassicalCardDetector(ctx)

    frame = np.full((290, 490, 3), 30, dtype=np.uint8)
    cv2.rectangle(frame, (120, 80), (310, 190), (240, 240, 240), -1)

    result = detector.detect(frame)
    assert result.visible, "detector should accept a clear card"
    assert result.candidate is not None, "detector should return a best candidate"
    assert result.candidates, "detector should expose candidate list for tracker matching"
    assert result.candidate.confidence >= config["detector"]["confidence"]["min_confidence"]


def test_tracker_continuity() -> None:
    tracker = CardTracker(
        max_lost_duration_s=0.5,
        match_max_distance_px=80.0,
        prediction_enabled=True,
        velocity_smoothing_alpha=1.0,
    )

    now = time.monotonic()
    tracker.initialize(make_pose(140.0, 90.0), now=now)
    tracker.update(make_pose(200.0, 90.0), now=now + 0.1)

    predicted = tracker.predicted_pose(frame_width=490, now=now + 0.2)
    assert predicted is not None, "tracker should predict through short occlusion"
    assert predicted.x > 200.0, "prediction should move forward using velocity"
    assert tracker.has_recent_track(now=now + 0.2), "short occlusion should stay alive"

    matched = tracker.match_candidate(
        [make_pose(265.0, 92.0), make_pose(420.0, 92.0, confidence=0.99)],
        now=now + 0.2,
    )
    assert matched is not None, "tracker should match the nearest candidate"
    assert matched.x == 265.0, "tracker should stay locked to the predicted position"
    assert not tracker.has_recent_track(now=now + 0.8), "track should expire after the timeout"


def main() -> int:
    test_detector_scoring()
    test_tracker_continuity()
    print("tracking continuity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())