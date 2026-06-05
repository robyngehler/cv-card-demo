#!/usr/bin/env python3
"""
Detailed preprocessing visualization script.
Shows every step of the detection pipeline to debug why workspace is detected instead of cards.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.app_context import create_app_context
from app.config_loader import load_config
from app.services.workspace_service import WorkspaceService


def save_and_show(img, name, output_dir="debug_pipeline"):
    """Save and print image info."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, name)
    cv2.imwrite(path, img)
    
    if len(img.shape) == 2:
        print(f"  {name}: {img.shape} (grayscale), range=[{img.min()}, {img.max()}]")
    else:
        print(f"  {name}: {img.shape} (color), range=[{img.min()}, {img.max()}]")


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

    grayscale = bool(preprocessing.get("grayscale", True))
    blur_kernel = int(preprocessing.get("blur_kernel", 5))
    threshold_mode = preprocessing.get("threshold_mode", "adaptive")
    canny_enabled = bool(preprocessing.get("canny_enabled", False))

    min_area_px = int(contour_filter.get("min_area_px", 1000))
    max_area_ratio = float(contour_filter.get("max_area_ratio", 0.8))

    print("Reading frame...")
    ret, raw_frame = cap.read()
    if not ret:
        print("ERROR: Cannot read from camera")
        sys.exit(1)

    print(f"Raw frame: {raw_frame.shape}")

    workspace_service.validate(raw_frame.shape)
    workspace_frame = workspace_service.transform(raw_frame)
    print(f"Workspace frame: {workspace_frame.shape}")
    print("")

    # Save raw workspace frame
    save_and_show(workspace_frame, "01_raw_workspace.jpg")

    # Convert to grayscale
    if grayscale and len(workspace_frame.shape) == 3:
        frame = cv2.cvtColor(workspace_frame, cv2.COLOR_BGR2GRAY)
    else:
        frame = workspace_frame.copy()

    save_and_show(frame, "02_grayscale.jpg")

    # Show histogram to understand value distribution
    hist = cv2.calcHist([frame], [0], None, [256], [0, 256])
    hist_img = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.normalize(hist, hist, 0, 256, cv2.NORM_MINMAX)
    for i in range(len(hist) - 1):
        cv2.line(hist_img, (i, 256 - int(hist[i])), (i + 1, 256 - int(hist[i + 1])), (0, 255, 0), 1)
    save_and_show(hist_img, "03_histogram.jpg")

    # Blur
    if blur_kernel > 1:
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        frame = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

    save_and_show(frame, "04_blurred.jpg")

    # Threshold
    if canny_enabled:
        mask = cv2.Canny(frame, 50, 150)
        save_and_show(mask, "05_canny_edges.jpg")
    elif threshold_mode == "otsu":
        _, mask = cv2.threshold(frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        save_and_show(mask, "05_threshold_otsu.jpg")
    else:
        mask = cv2.adaptiveThreshold(
            frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5,
        )
        save_and_show(mask, "05_threshold_adaptive.jpg")

    # Morphology
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    save_and_show(mask, "06_morphology_open.jpg")

    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    save_and_show(mask, "07_morphology_close.jpg")

    # Find contours
    contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

    print(f"\nFound {len(contours)} contours")

    # Draw all contours
    contour_img = cv2.cvtColor(workspace_frame, cv2.COLOR_BGR2RGB)
    cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)
    save_and_show(contour_img, "08_all_contours_drawn.jpg")

    # Analyze each contour
    frame_area = float(mask.shape[0] * mask.shape[1])
    print(f"\nContour Analysis (Total frame area: {frame_area:.0f}px):")
    print(f"Thresholds: area > {min_area_px}px, area < {frame_area * max_area_ratio:.0f}px")
    print("")

    sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]
    for i, contour in enumerate(sorted_contours, 1):
        area = cv2.contourArea(contour)
        rect = cv2.minAreaRect(contour)
        (cx, cy), (w, h), angle = rect

        if w <= 0 or h <= 0:
            continue

        aspect = max(w, h) / min(w, h)
        area_ratio = area / frame_area

        status = "✓" if area > min_area_px else "✗"
        print(f"{i}. Area={area:.0f}px ({area_ratio*100:.1f}%) Aspect={aspect:.2f} {status}")

    # Draw bounding boxes for top contours
    debug_img = cv2.cvtColor(workspace_frame, cv2.COLOR_BGR2RGB)
    for i, contour in enumerate(sorted_contours[:3]):
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.int32(box)
        color = (0, 255, 0) if i == 0 else (255, 165, 0)
        cv2.polylines(debug_img, [box], True, color, 2)

    save_and_show(debug_img, "09_top_3_contours.jpg")

    print("")
    print("✓ All images saved to debug_pipeline/")
    print("  Open 05_threshold*.jpg to see which threshold works best")
    print("  Open 08_all_contours_drawn.jpg to see what's being detected")
    print("  Open 09_top_3_contours.jpg to see largest contours (green=largest)")

    cap.release()


if __name__ == "__main__":
    main()
