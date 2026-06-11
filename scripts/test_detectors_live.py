#!/usr/bin/env python3
"""
Quick live test: grab a camera frame and test both classical and YOLO detectors.
Shows detection results, rejection counts, and confidence scores.

Usage:
  python scripts/test_detectors_live.py [classical|yolo|both]
"""
import sys
import time
import logging
import yaml
import cv2
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("test-detectors")

def grab_camera_frame():
    """Grab a single frame from camera with buffer flushed."""
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 4096)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # Read a few frames to flush buffer
    for _ in range(5):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("Could not read camera frame")

    return frame


def test_classical(frame, workspace):
    """Test classical detector on a frame."""
    print("\n" + "="*70)
    print("CLASSICAL DETECTOR TEST")
    print("="*70)

    from app.app_context import AppContext
    from app.cv.classical_card_detector import ClassicalCardDetector

    config = yaml.safe_load(open("config/config.yaml"))
    ctx = AppContext(config=config, logger=logger, runtime={}, services={})
    ctx.get_service = lambda name, default=None: workspace if name == "workspace" else default

    detector = ClassicalCardDetector(ctx)

    try:
        start = time.monotonic()
        result = detector.detect(workspace.transform(frame, workspace_name="card"))
        elapsed = time.monotonic() - start

        print(f"Time: {elapsed*1000:.1f} ms")
        print(f"Status: {result.status}")
        print(f"Visible: {result.visible}")
        print(f"Candidates: {result.candidates_count}")

        if result.candidate:
            print(f"\nTop candidate:")
            print(f"  Confidence: {result.candidate.confidence:.3f}")
            print(f"  Position: ({result.candidate.x:.0f}, {result.candidate.y:.0f})")
            print(f"  Size: {result.candidate.width:.0f}x{result.candidate.height:.0f} px (area={result.candidate.width*result.candidate.height:.0f} px²)")
            print(f"  Aspect ratio: {result.candidate.width/max(result.candidate.height, 0.1):.2f}")
            print(f"  Normalized: ({result.candidate.x_normalized:.2f}, {result.candidate.y_normalized:.2f})")

        if result.debug.get("rejection_counts"):
            print(f"\nRejection counts:")
            for k, v in result.debug["rejection_counts"].items():
                if v > 0:
                    print(f"  {k}: {v}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_yolo(frame, workspace):
    """Test YOLO detector on a frame."""
    print("\n" + "="*70)
    print("YOLO DETECTOR TEST")
    print("="*70)

    from ultralytics import YOLO
    from app.app_context import AppContext
    from app.cv.yolo_card_detector import YoloCardDetector

    config = yaml.safe_load(open("config/config.yaml"))
    ctx = AppContext(config=config, logger=logger, runtime={}, services={})
    ctx.get_service = lambda name, default=None: workspace if name == "workspace" else default

    detector = YoloCardDetector(ctx)

    if not detector.available:
        print(f"YOLO not available: {detector.status.get('last_error')}")
        return

    print(f"Model: {detector.status.get('model_path')}")
    print(f"Device: {detector.status.get('device')}")

    try:
        start = time.monotonic()
        result = detector.detect(workspace.transform(frame, workspace_name="card"))
        elapsed = time.monotonic() - start

        print(f"Time: {elapsed*1000:.1f} ms")
        print(f"Status: {result.status}")
        print(f"Visible: {result.visible}")
        print(f"Candidates: {result.candidates_count}")

        if result.candidate:
            print(f"\nTop candidate:")
            print(f"  Confidence: {result.candidate.confidence:.3f}")
            print(f"  Position: ({result.candidate.x:.0f}, {result.candidate.y:.0f})")
            print(f"  Size: {result.candidate.width:.0f}x{result.candidate.height:.0f} px")
            print(f"  Aspect ratio: {result.candidate.width/max(result.candidate.height, 0.1):.2f}")
            print(f"  Normalized: ({result.candidate.x_normalized:.2f}, {result.candidate.y_normalized:.2f})")
            print(f"  Label: {result.candidate.label}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    try:
        logger.info("Grabbing camera frame...")
        frame = grab_camera_frame()
        logger.info(f"Frame shape: {frame.shape}")

        # Setup workspace service
        from app.services.workspace_service import WorkspaceService
        from app.app_context import AppContext

        config = yaml.safe_load(open("config/config.yaml"))
        ctx = AppContext(config=config, logger=logger, runtime={}, services={})
        workspace = WorkspaceService(ctx)
        workspace.configure(config.get("workspace", {}))
        workspace.validate(frame.shape)

        logger.info(f"Workspace ready: card={workspace.get_dimensions('card')} px")

        test_mode = sys.argv[1] if len(sys.argv) > 1 else "both"

        if test_mode in ("classical", "both"):
            test_classical(frame, workspace)

        if test_mode in ("yolo", "both"):
            test_yolo(frame, workspace)

        print("\n" + "="*70)
        print("DONE")
        print("="*70)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
