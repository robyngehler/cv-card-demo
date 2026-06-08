#!/usr/bin/env python3
"""
Hand Interference Analysis – Detailed diagnostic when hand occludes/moves card.
Records confidence changes, contour properties, and generates debug images.
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


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def apply_morphology(mask, preprocessing):
    if not bool(preprocessing.get("morphology_enabled", True)):
        return mask

    kernel_size = max(1, int(preprocessing.get("morphology_kernel_size", 3)))
    if kernel_size % 2 == 0:
        kernel_size += 1

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    close_iterations = max(0, int(preprocessing.get("morphology_close_iterations", 2)))
    open_iterations = max(0, int(preprocessing.get("morphology_open_iterations", 1)))

    if close_iterations > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=close_iterations)
    if open_iterations > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=open_iterations)
    return mask


def main():
    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)

    workspace_service = WorkspaceService(ctx)
    workspace_config = config.get("workspace", {})
    workspace_service.configure(workspace_config)

    detector = ClassicalCardDetector(ctx)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        sys.exit(1)

    detector_config = config.get("detector", {})
    preprocessing = detector_config.get("preprocessing", {})
    contour_filter = detector_config.get("contour_filter", {})
    confidence_cfg = detector_config.get("confidence", {})

    print("Hand Interference Analysis")
    print("============================")
    print("Instructions:")
    print("  1. Show card alone in frame")
    print("  2. Press SPACE to capture baseline")
    print("  3. Move hand into frame over the card")
    print("  4. Press SPACE to capture hand-on-card state")
    print("  5. Move hand out of frame")
    print("  6. Press SPACE to capture final state")
    print("  7. Press 'q' to quit")
    print("")

    min_area_px = int(contour_filter.get("min_area_px", 1500))
    max_area_ratio = float(contour_filter.get("max_area_ratio", 0.8))
    min_aspect_ratio = float(contour_filter.get("min_aspect_ratio", 1.2))
    max_aspect_ratio = float(contour_filter.get("max_aspect_ratio", 2.2))
    min_confidence = float(confidence_cfg.get("min_confidence", 0.35))
    expected_card_area_px = float(confidence_cfg.get("expected_card_area_px", 3200.0))
    target_aspect_ratio = float(confidence_cfg.get("target_aspect_ratio", 1.65))
    aspect_tolerance = max(0.01, float(confidence_cfg.get("aspect_tolerance", 0.55)))
    weight_area = float(confidence_cfg.get("weight_area", 0.35))
    weight_aspect = float(confidence_cfg.get("weight_aspect", 0.35))
    weight_rectangularity = float(confidence_cfg.get("weight_rectangularity", 0.30))

    captured_states = []
    frame_count = 0

    try:
        while True:
            ret, raw_frame = cap.read()
            if not ret:
                print("ERROR: Cannot read from camera")
                break

            try:
                workspace_service.validate(raw_frame.shape)
                workspace_frame = workspace_service.transform(raw_frame)
            except Exception as exc:
                print(f"Workspace error: {exc}")
                break

            result = detector.detect(workspace_frame)
            debug_frame = detector.draw_debug(workspace_frame, result)

            # Show info overlay
            info_text = (
                f"Visible: {result.visible} | "
                f"Confidence: {(result.candidate.confidence if result.candidate is not None else 0.0):.3f} | "
                f"Candidates: {result.candidates_count}"
            )
            cv2.putText(
                debug_frame,
                info_text,
                (10, 270),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
            )
            cv2.putText(
                debug_frame,
                "Press SPACE to capture, 'q' to quit",
                (10, 285),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (200, 200, 200),
                1,
            )

            cv2.imshow("Hand Interference Test", debug_frame)

            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                print("\nQuitting...")
                break
            elif key == ord(" "):
                state_name = {
                    0: "baseline (card alone)",
                    1: "hand on card",
                    2: "hand removed",
                }.get(len(captured_states), f"state_{len(captured_states)}")

                captured_states.append({
                    "name": state_name,
                    "frame": workspace_frame.copy(),
                    "result": result,
                    "visible": result.visible,
                    "confidence": result.candidate.confidence if result.candidate else 0.0,
                    "candidates": result.candidates_count,
                    "candidate": result.candidate,
                })

                print(f"\n✓ Captured state {len(captured_states)}: {state_name}")
                print(f"  Visible: {result.visible}")
                print(f"  Candidates: {result.candidates_count}")
                if result.candidate:
                    print(f"  Confidence: {result.candidate.confidence:.3f}")
                    print(f"  Area: {result.candidate.width * result.candidate.height:.0f}px")
                    print(f"  Aspect: {max(result.candidate.width, result.candidate.height) / min(result.candidate.width, result.candidate.height):.2f}")

                if len(captured_states) >= 3:
                    print("\n✓ All 3 states captured! Processing...")
                    break

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        cv2.destroyAllWindows()

    if len(captured_states) < 2:
        print("Not enough states captured. Need at least 2 states.")
        cap.release()
        return

    # Analyze captured states
    print("\n" + "=" * 70)
    print("DETAILED ANALYSIS")
    print("=" * 70)

    output_dir = "debug_hand_interference"
    os.makedirs(output_dir, exist_ok=True)

    for i, state in enumerate(captured_states):
        print(f"\nState {i + 1}: {state['name'].upper()}")
        print("-" * 70)

        frame = state["frame"]
        result = state["result"]

        # Get full contour analysis
        preprocessing = config.get("detector", {}).get("preprocessing", {})
        grayscale = bool(preprocessing.get("grayscale", True))
        blur_kernel = int(preprocessing.get("blur_kernel", 5))
        threshold_mode = preprocessing.get("threshold_mode", "otsu")

        gray = frame.copy()
        if grayscale and len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if blur_kernel > 1:
            if blur_kernel % 2 == 0:
                blur_kernel += 1
            gray = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)

        if threshold_mode == "otsu":
            _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            mask = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5,
            )

        mask = apply_morphology(mask, preprocessing)

        contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

        frame_area = float(mask.shape[0] * mask.shape[1])

        print(f"Contours found: {len(contours)}")
        print(f"Card visible: {state['visible']}")
        print(f"Confidence: {state['confidence']:.3f} (threshold: {min_confidence:.2f})")
        print(f"Candidates accepted: {state['candidates']}")

        # Analyze top contours
        sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        print(f"\nTop 5 contours:")
        for j, contour in enumerate(sorted_contours, 1):
            area = cv2.contourArea(contour)
            rect = cv2.minAreaRect(contour)
            (cx, cy), (w, h), angle = rect

            if w <= 0 or h <= 0:
                continue

            aspect = max(w, h) / min(w, h)
            rect_area = float(w * h)
            area_score = clamp(area / expected_card_area_px)
            aspect_score = clamp(1.0 - abs(aspect - target_aspect_ratio) / aspect_tolerance)
            rectangularity_score = 0.0 if rect_area <= 0.0 else clamp(area / rect_area)
            confidence = clamp(
                (weight_area * area_score)
                + (weight_aspect * aspect_score)
                + (weight_rectangularity * rectangularity_score)
            )

            status_area = "✓" if (area > min_area_px and area < frame_area * max_area_ratio) else "✗"
            status_aspect = "✓" if (aspect > min_aspect_ratio and aspect < max_aspect_ratio) else "✗"
            status_conf = "✓" if confidence >= min_confidence else "✗"

            print(
                f"  {j}. Area={area:.0f}px({area_score:.2f}) Aspect={aspect:.2f}({aspect_score:.2f}) "
                f"Rect={rectangularity_score:.2f} Conf={confidence:.3f} {status_area}{status_aspect}{status_conf}"
            )

        # Save images
        debug_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        cv2.imwrite(f"{output_dir}/state_{i + 1}_{state['name']}_frame.jpg", debug_img)
        cv2.imwrite(f"{output_dir}/state_{i + 1}_{state['name']}_mask.jpg", mask)

        # Draw contours
        contour_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 1)
        cv2.imwrite(f"{output_dir}/state_{i + 1}_{state['name']}_contours.jpg", contour_img)

    # Comparison
    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    if len(captured_states) >= 2:
        baseline = captured_states[0]
        with_hand = captured_states[1]

        print(f"\nBaseline ({baseline['name']}):")
        print(f"  Visible: {baseline['visible']}")
        print(f"  Confidence: {baseline['confidence']:.3f}")
        print(f"  Candidates: {baseline['candidates']}")

        print(f"\nWith Hand ({with_hand['name']}):")
        print(f"  Visible: {with_hand['visible']}")
        print(f"  Confidence: {with_hand['confidence']:.3f}")
        print(f"  Candidates: {with_hand['candidates']}")

        conf_diff = baseline["confidence"] - with_hand["confidence"]
        conf_pct = (conf_diff / baseline["confidence"] * 100) if baseline["confidence"] > 0 else 0

        print(f"\nChange:")
        print(f"  Confidence drop: {conf_diff:.3f} ({conf_pct:.1f}%)")
        print(f"  Visible: {baseline['visible']} → {with_hand['visible']}")

        if conf_pct > 30:
            print(f"\n⚠️  SIGNIFICANT CONFIDENCE DROP ({conf_pct:.1f}%)")
            print("    Hand occlusion causes detection failure")
        elif conf_pct > 10:
            print(f"\n⚠️  MODERATE CONFIDENCE DROP ({conf_pct:.1f}%)")
            print("    Hand interference noticeable")

    print(f"\n✓ Debug images saved to {output_dir}/")
    print("  Compare state_1_*_mask.jpg to see threshold differences")
    print("  Compare state_1_*_contours.jpg to see contour fragmentation")

    cap.release()


if __name__ == "__main__":
    main()
