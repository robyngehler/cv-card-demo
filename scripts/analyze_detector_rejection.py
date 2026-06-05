#!/usr/bin/env python3
"""
Ultra-detailed detector analysis - shows exact reason each contour is rejected.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.app_context import create_app_context
from app.config_loader import load_config
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

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        sys.exit(1)

    detector_config = config.get("detector", {})
    preprocessing = detector_config.get("preprocessing", {})
    contour_filter = detector_config.get("contour_filter", {})
    confidence_cfg = detector_config.get("confidence", {})

    print("DETECTOR CONFIGURATION")
    print("======================")
    print(f"Preprocessing: {preprocessing}")
    print(f"Contour Filter: {contour_filter}")
    print(f"Confidence: {confidence_cfg}")
    print("")

    grayscale = bool(preprocessing.get("grayscale", True))
    blur_kernel = int(preprocessing.get("blur_kernel", 5))
    threshold_mode = preprocessing.get("threshold_mode", "adaptive")

    min_area_px = int(contour_filter.get("min_area_px", 1000))
    max_area_ratio = float(contour_filter.get("max_area_ratio", 0.8))
    min_aspect_ratio = float(contour_filter.get("min_aspect_ratio", 1.2))
    max_aspect_ratio = float(contour_filter.get("max_aspect_ratio", 2.2))
    min_confidence = float(confidence_cfg.get("min_confidence", 0.5))
    expected_card_area_px = float(confidence_cfg.get("expected_card_area_px", 3200.0))
    target_aspect_ratio = float(confidence_cfg.get("target_aspect_ratio", 1.65))
    aspect_tolerance = max(0.01, float(confidence_cfg.get("aspect_tolerance", 0.55)))
    weight_area = float(confidence_cfg.get("weight_area", 0.35))
    weight_aspect = float(confidence_cfg.get("weight_aspect", 0.35))
    weight_rectangularity = float(confidence_cfg.get("weight_rectangularity", 0.30))

    print("Reading one frame...")
    ret, raw_frame = cap.read()
    if not ret:
        print("ERROR: Cannot read from camera")
        sys.exit(1)

    workspace_service.validate(raw_frame.shape)
    workspace_frame = workspace_service.transform(raw_frame)

    print(f"Workspace frame: {workspace_frame.shape}")
    print("")

    frame = workspace_frame
    if grayscale and len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if blur_kernel > 1:
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        frame = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

    if threshold_mode == "otsu":
        _, mask = cv2.threshold(frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        mask = cv2.adaptiveThreshold(
            frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5,
        )

    mask = apply_morphology(mask, preprocessing)

    contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

    frame_area = float(mask.shape[0] * mask.shape[1])
    print(f"Found {len(contours)} contours")
    print(f"Frame area: {frame_area:.0f}px | Area threshold: [{min_area_px}, {frame_area * max_area_ratio:.0f}]")
    print("")
    print("TOP 10 CONTOURS BY AREA:")
    print("========================")

    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

    for i, contour in enumerate(sorted_contours, 1):
        area = float(cv2.contourArea(contour))
        rect = cv2.minAreaRect(contour)
        (center_x, center_y), (width, height), theta_deg = rect

        if width <= 0 or height <= 0:
            print(f"{i}. INVALID RECT (width={width}, height={height})")
            continue

        aspect_ratio = max(width, height) / min(width, height)
        
        reasons = []
        if area < min_area_px:
            reasons.append(f"area too small ({area:.0f} < {min_area_px})")
        if area > frame_area * max_area_ratio:
            reasons.append(f"area too large ({area:.0f} > {frame_area * max_area_ratio:.0f})")
        if aspect_ratio < min_aspect_ratio:
            reasons.append(f"aspect ratio too small ({aspect_ratio:.2f} < {min_aspect_ratio:.2f})")
        if aspect_ratio > max_aspect_ratio:
            reasons.append(f"aspect ratio too large ({aspect_ratio:.2f} > {max_aspect_ratio:.2f})")

        rect_area = float(width * height)
        area_score = clamp(area / expected_card_area_px)
        aspect_score = clamp(1.0 - abs(aspect_ratio - target_aspect_ratio) / aspect_tolerance)
        rectangularity_score = 0.0 if rect_area <= 0.0 else clamp(area / rect_area)
        confidence = clamp(
            (weight_area * area_score)
            + (weight_aspect * aspect_score)
            + (weight_rectangularity * rectangularity_score)
        )

        if confidence < min_confidence:
            reasons.append(f"confidence too low ({confidence:.2f} < {min_confidence:.2f})")

        status = "✓ ACCEPT" if not reasons else f"✗ REJECT"
        print(
            f"{i}. Area={area:.0f}px Aspect={aspect_ratio:.2f} Rect={rectangularity_score:.2f} "
            f"Confidence={confidence:.2f} | {status}"
        )
        if reasons:
            for reason in reasons:
                print(f"   └─ {reason}")

    print("")
    print("SUGGESTIONS FOR TUNING:")
    print("=======================")
    
    if sorted_contours:
        largest_area = cv2.contourArea(sorted_contours[0])
        print(f"✓ Largest detected area: {largest_area:.0f}px")
        if largest_area < min_area_px:
            suggested = int(largest_area * 0.7)
            print(f"  → Try lowering min_area_px to ~{suggested}px")
        
        largest_rect = cv2.minAreaRect(sorted_contours[0])
        largest_width, largest_height = largest_rect[1]
        largest_aspect = max(largest_width, largest_height) / min(largest_width, largest_height)
        print(f"✓ Largest detected aspect ratio: {largest_aspect:.2f}")
        if largest_aspect < min_aspect_ratio:
            print(f"  → Try lowering min_aspect_ratio to ~{max(1.0, largest_aspect * 0.9):.2f}")
        elif largest_aspect > max_aspect_ratio:
            print(f"  → Try raising max_aspect_ratio to ~{largest_aspect * 1.1:.2f}")
    else:
        print("✗ No contours found at all - check threshold_mode or lighting")

    cap.release()


if __name__ == "__main__":
    main()
