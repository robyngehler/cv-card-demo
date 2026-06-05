#!/usr/bin/env python3
"""
Simulate hand occlusion with synthetic images.
Creates test scenarios: card alone, card with hand, card after hand.
Shows how confidence changes.
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


def create_card_image(width: int = 490, height: int = 290) -> np.ndarray:
    """Create synthetic card image."""
    frame = np.full((height, width, 3), 40, dtype=np.uint8)  # Dark workspace
    
    # Card positioned in center
    card_x, card_y = 95, 60
    card_w, card_h = 300, 170
    
    # White card
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (220, 220, 220), -1)
    
    # Card border
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (50, 50, 50), 2)
    
    # Text
    cv2.putText(
        frame, "BUSINESS CARD", (card_x + 40, card_y + 50),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (50, 50, 50), 2
    )
    cv2.putText(
        frame, "Name | Company", (card_x + 60, card_y + 100),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1
    )
    
    return frame


def add_hand_overlay(frame, hand_type="partial"):
    """Add synthetic hand to occlude card."""
    frame = frame.copy()
    
    if hand_type == "light_touch":
        # Hand touches top-right corner of card
        hand_poly = np.array([
            [350, 70],   # Start at card top-right
            [390, 50],   # Hand extends up
            [420, 75],
            [400, 120],
        ], dtype=np.int32)
        cv2.fillPoly(frame, [hand_poly], (180, 160, 140))  # Skin tone
        
    elif hand_type == "partial":
        # Hand covers ~30% of card
        hand_poly = np.array([
            [300, 80],
            [380, 50],
            [420, 100],
            [350, 150],
        ], dtype=np.int32)
        cv2.fillPoly(frame, [hand_poly], (180, 160, 140))
        
    elif hand_type == "heavy":
        # Hand heavily occludes card (~50%)
        hand_poly = np.array([
            [200, 60],
            [350, 40],
            [420, 120],
            [280, 160],
        ], dtype=np.int32)
        cv2.fillPoly(frame, [hand_poly], (180, 160, 140))
    
    return frame


def main():
    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)

    workspace_service = WorkspaceService(ctx)
    workspace_config = config.get("workspace", {})
    workspace_service.configure(workspace_config)

    detector = ClassicalCardDetector(ctx)

    output_dir = "debug_hand_occlusion_synthetic"
    os.makedirs(output_dir, exist_ok=True)

    print("Synthetic Hand Occlusion Test")
    print("=" * 70)
    print("")

    scenarios = [
        ("01_card_alone", None),
        ("02_light_touch", "light_touch"),
        ("03_partial_occlusion", "partial"),
        ("04_heavy_occlusion", "heavy"),
        ("05_card_clear", None),
    ]

    results = []

    for scenario_name, hand_type in scenarios:
        print(f"\n{scenario_name.upper()}")
        print("-" * 70)

        # Create frame
        frame = create_card_image()
        if hand_type:
            frame = add_hand_overlay(frame, hand_type)

        # Save raw frame
        cv2.imwrite(f"{output_dir}/{scenario_name}_frame.jpg", frame)

        # Run detector
        result = detector.detect(frame)
        debug_frame = detector.draw_debug(frame, result)

        # Save debug frame
        cv2.imwrite(f"{output_dir}/{scenario_name}_detected.jpg", debug_frame)

        # Analyze
        print(f"Card visible: {result.visible}")
        print(f"Candidates: {result.candidates_count}")
        if result.candidate:
            print(f"Confidence: {result.candidate.confidence:.3f}")
            print(f"Area: {result.candidate.width * result.candidate.height:.0f}px")
            print(f"Aspect: {max(result.candidate.width, result.candidate.height) / min(result.candidate.width, result.candidate.height):.2f}")
            print(f"Position (x_norm): {result.candidate.x_normalized:.3f}")
            status = "✓ DETECT" if result.visible else "✗ LOST"
        else:
            print(f"Confidence: 0.000")
            status = "✗ LOST"

        results.append({
            "name": scenario_name,
            "visible": result.visible,
            "confidence": result.candidate.confidence if result.candidate else 0.0,
            "candidates": result.candidates_count,
            "status": status,
        })

        print(f"Status: {status}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n{'Scenario':<25} {'Visible':<10} {'Confidence':<15} {'Status':<10}")
    print("-" * 70)
    for res in results:
        print(f"{res['name']:<25} {str(res['visible']):<10} {res['confidence']:.3f} {res['status']:<10}")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    baseline_conf = results[0]["confidence"]
    light_touch_conf = results[1]["confidence"]
    partial_conf = results[2]["confidence"]
    heavy_conf = results[3]["confidence"]

    print(f"\nBaseline (card alone): {baseline_conf:.3f}")
    print(f"Light touch:          {light_touch_conf:.3f} (drop: {baseline_conf - light_touch_conf:.3f}, {(baseline_conf - light_touch_conf) / baseline_conf * 100:.1f}%)")
    print(f"Partial occlusion:    {partial_conf:.3f} (drop: {baseline_conf - partial_conf:.3f}, {(baseline_conf - partial_conf) / baseline_conf * 100:.1f}%)")
    print(f"Heavy occlusion:      {heavy_conf:.3f} (drop: {baseline_conf - heavy_conf:.3f}, {(baseline_conf - heavy_conf) / baseline_conf * 100:.1f}%)")

    threshold = config.get("detector", {}).get("confidence", {}).get("min_confidence", 0.35)
    print(f"\nDetection threshold: {threshold:.3f}")

    if light_touch_conf < threshold:
        print(f"⚠️  Light touch causes detection LOSS")
    if partial_conf < threshold:
        print(f"⚠️  Partial occlusion causes detection LOSS")
    if heavy_conf < threshold:
        print(f"⚠️  Heavy occlusion causes detection LOSS")

    print(f"\n✓ Test images saved to {output_dir}/")
    print("  Compare *_frame.jpg (input) vs *_detected.jpg (output)")
    print("  Check confidence drop as hand occlusion increases")


if __name__ == "__main__":
    main()
