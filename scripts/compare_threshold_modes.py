#!/usr/bin/env python3
"""
Quick comparison of different threshold modes on the current workspace.
Tests: adaptive, otsu, canny
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.app_context import create_app_context
from app.config_loader import load_config
from app.services.workspace_service import WorkspaceService


def analyze_threshold_mode(frame, mode, name):
    """Apply threshold and analyze results."""
    print(f"\n{name.upper()}")
    print("=" * 50)

    if mode == "otsu":
        _, mask = cv2.threshold(frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif mode == "canny":
        mask = cv2.Canny(frame, 50, 150)
    else:  # adaptive
        mask = cv2.adaptiveThreshold(
            frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5,
        )

    # Morphology
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find contours
    contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

    print(f"Contours found: {len(contours)}")

    # Analyze top contours
    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    print(f"\nTop 5 contours:")
    for i, contour in enumerate(sorted_contours, 1):
        area = cv2.contourArea(contour)
        rect = cv2.minAreaRect(contour)
        (cx, cy), (w, h), angle = rect

        if w <= 0 or h <= 0:
            continue

        aspect = max(w, h) / min(w, h)
        
        # Check if it passes filters
        min_area = 1000
        max_area = 142100 * 0.8
        min_aspect = 1.2
        max_aspect = 2.2
        
        passes_area = min_area < area < max_area
        passes_aspect = min_aspect < aspect < max_aspect
        status = "✓ PASS" if (passes_area and passes_aspect) else "✗ FAIL"
        
        print(f"  {i}. Area={area:.0f}px Aspect={aspect:.2f} {status}")
        if not passes_area:
            print(f"      (area out of range [{min_area}, {max_area:.0f}])")
        if not passes_aspect:
            print(f"      (aspect out of range [{min_aspect}, {max_aspect}])")

    cv2.imwrite(f"debug_pipeline/threshold_compare_{mode}.jpg", mask)
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

    print("Reading frame...")
    ret, raw_frame = cap.read()
    if not ret:
        print("ERROR: Cannot read from camera")
        sys.exit(1)

    workspace_service.validate(raw_frame.shape)
    workspace_frame = workspace_service.transform(raw_frame)

    # Convert to grayscale
    gray = cv2.cvtColor(workspace_frame, cv2.COLOR_BGR2GRAY)

    # Blur
    blur_kernel = 5
    gray = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)

    print(f"Workspace: {workspace_frame.shape}")
    print(f"Testing different threshold modes...")

    # Test all three modes
    analyze_threshold_mode(gray, "adaptive", "Adaptive Threshold (current)")
    analyze_threshold_mode(gray, "otsu", "OTSU Threshold")
    analyze_threshold_mode(gray, "canny", "Canny Edge Detection")

    print("\n" + "=" * 50)
    print("RECOMMENDATION:")
    print("=" * 50)
    print("✓ All images saved to debug_pipeline/threshold_compare_*.jpg")
    print("✓ OTSU is usually better for high-contrast images (dark workspace, light cards)")
    print("✓ Try: detector.threshold_mode = 'otsu'")

    cap.release()


if __name__ == "__main__":
    main()
