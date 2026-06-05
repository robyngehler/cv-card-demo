#!/usr/bin/env python3
"""
Card Detector Batch Test - No Display Required

This script processes test images and saves debug visualizations to disk.
Use this on headless systems or in CI pipelines.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.app_context import create_app_context
from app.config_loader import load_config
from app.cv.classical_card_detector import ClassicalCardDetector
from app.services.workspace_service import WorkspaceService


def create_test_card_image(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a synthetic test image with a realistic business card."""
    frame = np.full((height, width, 3), 80, dtype=np.uint8)
    
    card_x, card_y = 150, 120
    card_width, card_height = 320, 180
    
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_width, card_y + card_height), (240, 240, 240), -1)
    
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_width, card_y + card_height), (50, 50, 50), 2)
    
    cv2.putText(
        frame,
        "BUSINESS CARD",
        (card_x + 40, card_y + 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (50, 50, 50),
        2,
    )
    cv2.putText(
        frame,
        "Name | Company",
        (card_x + 40, card_y + 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (100, 100, 100),
        1,
    )
    
    return frame


def main():
    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)

    workspace_service = WorkspaceService(ctx)
    workspace_config = config.get("workspace", {})
    workspace_service.configure(workspace_config)

    detector = ClassicalCardDetector(ctx)

    output_dir = "debug_frames"
    os.makedirs(output_dir, exist_ok=True)

    print("Card Detector Batch Test")
    print("========================")
    print(f"Output: {output_dir}/")
    print(f"Workspace mode: {workspace_service.status.mode}")
    print("")

    raw_frame = create_test_card_image(width=640, height=480)
    print("[1] Test with synthetic card image")

    try:
        workspace_service.validate(raw_frame.shape)
        workspace_frame = workspace_service.transform(raw_frame)
    except Exception as exc:
        print(f"  ✗ Workspace error: {exc}")
        return 1

    result = detector.detect(workspace_frame)
    debug_frame = detector.draw_debug(workspace_frame, result)

    output_file = os.path.join(output_dir, "test_card_detection.png")
    cv2.imwrite(output_file, debug_frame)

    if result.visible and result.candidate:
        print(f"  ✓ Card detected!")
        print(f"    Confidence: {result.candidate.confidence:.3f}")
        print(f"    Normalized X: {result.candidate.x_normalized:.3f}")
        print(f"    Angle: {result.candidate.theta_deg:.1f}°")
        print(f"    Saved to: {output_file}")
    else:
        print(f"  ✗ No card detected")
        print(f"    Candidates evaluated: {result.candidates_count}")
        print(f"    Saved to: {output_file}")

    print("\nTest complete. View output images in", output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
