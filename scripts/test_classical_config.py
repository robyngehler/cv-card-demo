#!/usr/bin/env python3
"""
Test classical detector with different config variations.
Shows which area/confidence checks are rejecting detections.
"""
import sys
import yaml
import numpy as np
import cv2

def test_config(config_path, description=""):
    """Load config and show detector parameter values."""
    config = yaml.safe_load(open(config_path))

    detector_cfg = config.get("detector", {})
    contour = detector_cfg.get("contour_filter", {})
    confidence = detector_cfg.get("confidence", {})

    print(f"\n{'='*70}")
    print(f"CONFIG: {description}")
    print(f"{'='*70}")
    print(f"min_area_px: {contour.get('min_area_px')}")
    print(f"max_area_ratio: {contour.get('max_area_ratio')}")
    print(f"min_aspect_ratio: {contour.get('min_aspect_ratio')}")
    print(f"max_aspect_ratio: {contour.get('max_aspect_ratio')}")
    print(f"min_rectangularity: {contour.get('min_rectangularity', 'N/A')}")
    print(f"min_solidity: {contour.get('min_solidity', 'N/A')}")
    print(f"require_quadrilateral: {contour.get('require_quadrilateral', 'N/A')}")
    print(f"border_margin_px: {contour.get('border_margin_px', 'N/A')}")
    print()
    print(f"min_confidence: {confidence.get('min_confidence')}")
    print(f"expected_card_area_px: {confidence.get('expected_card_area_px')}")
    print(f"min_area_similarity: {confidence.get('min_area_similarity', 'N/A')}")
    print(f"target_aspect_ratio: {confidence.get('target_aspect_ratio')}")
    print(f"aspect_tolerance: {confidence.get('aspect_tolerance')}")
    print(f"weight_area: {confidence.get('weight_area')}")
    print(f"weight_aspect: {confidence.get('weight_aspect')}")
    print(f"weight_rectangularity: {confidence.get('weight_rectangularity')}")


def test_workspace_sizes():
    """Show workspace and frame sizes."""
    config = yaml.safe_load(open("config/config.yaml"))

    workspace = config.get("workspace", {}).get("card", {})
    live_proc = config.get("camera", {}).get("live_processing", {})
    camera = config.get("camera", {})

    print(f"\n{'='*70}")
    print("FRAME & WORKSPACE SIZES")
    print(f"{'='*70}")
    print(f"Camera: {camera.get('width')}x{camera.get('height')} @ {camera.get('fps')} fps")
    print(f"Live processing: {live_proc.get('width')}x{live_proc.get('height')} (downscaled)")

    rect = workspace.get("rect_px", {})
    print(f"Workspace rect (on live frame): {rect.get('width')}x{rect.get('height')} px")
    workspace_area = rect.get('width', 0) * rect.get('height', 0)
    print(f"  Area: {workspace_area} px²")

    # Estimate typical business card size in workspace
    card_width_mm = 90  # typical business card
    card_height_mm = 50
    workspace_width_mm = 300  # assuming ~300mm workspace width

    card_width_px = (card_width_mm / workspace_width_mm) * rect.get('width', 0)
    card_height_px = (card_height_mm / workspace_width_mm) * rect.get('height', 0)
    card_area_px = card_width_px * card_height_px

    print(f"\nEstimated business card in workspace:")
    print(f"  ~{card_width_px:.0f}x{card_height_px:.0f} px")
    print(f"  Area: ~{card_area_px:.0f} px²")

    expected = config.get("detector", {}).get("confidence", {}).get("expected_card_area_px")
    print(f"\nConfig expects card area: {expected} px²")

    if expected and card_area_px > 0:
        similarity_score = 1.0 - abs(card_area_px - expected) / max(expected, 1.0)
        min_area_similarity = config.get("detector", {}).get("confidence", {}).get("min_area_similarity", 0.0)
        print(f"Similarity score would be: {similarity_score:.2f}")
        print(f"Required minimum: {min_area_similarity:.2f}")
        if similarity_score >= min_area_similarity:
            print("✓ Would pass area check")
        else:
            print(f"✗ Would FAIL (need {min_area_similarity - similarity_score:.2f} more)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("CLASSICAL DETECTOR CONFIG ANALYSIS")
    print("="*70)

    # Compare current vs commits
    test_config("config/config.yaml", "CURRENT")

    # Show frame/workspace info
    test_workspace_sizes()

    print("\nTo debug live: use /run to start backend, then python scripts/test_classical_detector_live.py")
