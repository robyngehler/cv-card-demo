#!/usr/bin/env python3
"""
Test detectors using a frame grabbed from the running backend API.
This avoids camera conflicts when the backend is already running.
"""
import sys
import time
import logging
import yaml
import cv2
import io
import requests
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("test-detectors-api")

def grab_frame_from_api(url="http://localhost:8000"):
    """Grab a frame from the backend's live frame API."""
    try:
        response = requests.get(f"{url}/api/live-frame?mode=run", timeout=5)
        response.raise_for_status()

        # Decode JPEG
        frame_array = np.frombuffer(response.content, dtype=np.uint8)
        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

        if frame is None:
            raise RuntimeError("Could not decode JPEG frame")

        return frame
    except Exception as e:
        raise RuntimeError(f"Could not fetch frame from API: {e}") from e


def test_classical(frame, workspace):
    """Test classical detector."""
    print("\n" + "="*70)
    print("CLASSICAL DETECTOR TEST")
    print("="*70)

    from app.app_context import AppContext
    from app.cv.classical_card_detector import ClassicalCardDetector

    config = yaml.safe_load(open("config/config.yaml"))
    ctx = AppContext(config=config, logger=logger, runtime={}, services={})
    ctx.get_service = lambda name, default=None: workspace if name == "workspace" else default

    detector = ClassicalCardDetector(ctx)
    workspace_frame = workspace.transform(frame, workspace_name="card")

    try:
        start = time.monotonic()
        result = detector.detect(workspace_frame)
        elapsed = time.monotonic() - start

        print(f"Time: {elapsed*1000:.1f} ms")
        print(f"Status: {result.status}")
        print(f"Visible: {result.visible}")
        print(f"Candidates: {result.candidates_count}")

        if result.candidate:
            print(f"\n✓ TOP CANDIDATE:")
            print(f"  Confidence: {result.candidate.confidence:.3f}")
            print(f"  Position: ({result.candidate.x:.0f}, {result.candidate.y:.0f})")
            print(f"  Size: {result.candidate.width:.0f}x{result.candidate.height:.0f} px")
            print(f"  Area: {result.candidate.width*result.candidate.height:.0f} px²")
            print(f"  Aspect: {result.candidate.width/max(result.candidate.height, 0.1):.2f}")
            print(f"  Normalized score: {result.candidate.x_normalized:.2f}")
        else:
            print(f"\n✗ No candidate found")

        if result.debug.get("rejection_counts"):
            rejections = {k: v for k, v in result.debug["rejection_counts"].items() if v > 0}
            if rejections:
                print(f"\nRejection summary: {rejections}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_yolo(frame, workspace):
    """Test YOLO detector."""
    print("\n" + "="*70)
    print("YOLO DETECTOR TEST")
    print("="*70)

    from app.app_context import AppContext
    from app.cv.yolo_card_detector import YoloCardDetector

    config = yaml.safe_load(open("config/config.yaml"))
    ctx = AppContext(config=config, logger=logger, runtime={}, services={})
    ctx.get_service = lambda name, default=None: workspace if name == "workspace" else default

    detector = YoloCardDetector(ctx)

    if not detector.available:
        print(f"✗ YOLO not available: {detector.status.get('last_error')}")
        return

    print(f"Model: {detector.status.get('model_path')}")
    print(f"Device: {detector.status.get('device')}")
    workspace_frame = workspace.transform(frame, workspace_name="card")

    try:
        start = time.monotonic()
        result = detector.detect(workspace_frame)
        elapsed = time.monotonic() - start

        print(f"Time: {elapsed*1000:.1f} ms")
        print(f"Status: {result.status}")
        print(f"Visible: {result.visible}")
        print(f"Candidates: {result.candidates_count}")

        if result.candidate:
            print(f"\n✓ TOP CANDIDATE:")
            print(f"  Confidence: {result.candidate.confidence:.3f}")
            print(f"  Position: ({result.candidate.x:.0f}, {result.candidate.y:.0f})")
            print(f"  Size: {result.candidate.width:.0f}x{result.candidate.height:.0f} px")
            print(f"  Label: {result.candidate.label}")
            print(f"  Normalized score: {result.candidate.x_normalized:.2f}")
        else:
            print(f"\n✗ No candidate found")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    try:
        logger.info("Fetching frame from backend API...")
        frame = grab_frame_from_api()
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
        print("✓ TESTS COMPLETE")
        print("="*70)

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
