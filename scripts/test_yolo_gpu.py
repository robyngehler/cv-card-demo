#!/usr/bin/env python3
"""Test YOLO models with explicit GPU forcing."""
import sys
import os
import requests
import numpy as np
import cv2
import torch

# Ensure CUDA is initialized BEFORE importing ultralytics
torch.cuda.is_available()
torch.cuda.init()

from ultralytics import YOLO

def test_model_on_gpu(model_name="id-card"):
    """Test a YOLO model on GPU with explicit device forcing."""

    models = {
        "visiting_card": "models/yolov8_visiting_card.pt",
        "id-card": "models/YOLO-id-card.pt",
    }

    model_path = models.get(model_name)
    if not model_path:
        print(f"Unknown model: {model_name}")
        return

    print("="*70)
    print(f"YOLO MODEL GPU TEST: {model_name}")
    print("="*70)
    print(f"CUDA available: {torch.cuda.is_available()}")
    print(f"CUDA version: {torch.version.cuda}")
    print()

    # Grab frame from running backend
    print("Fetching frame from backend...")
    try:
        response = requests.get("http://localhost:8000/api/live-frame?mode=run", timeout=5)
        frame = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
        print(f"✓ Frame shape: {frame.shape}")
    except Exception as e:
        print(f"✗ Failed to get frame: {e}")
        return

    print()
    print(f"Loading {model_path}...")
    try:
        model = YOLO(model_path)
        print(f"Initial device: {model.device}")

        # Explicitly move to GPU
        print("Moving model to cuda:0...")
        model.to("cuda:0")
        print(f"After move device: {model.device}")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return

    print()
    print("Running inference...")
    try:
        results = model.predict(source=frame, verbose=False, conf=0.25, device="cuda:0")

        if results:
            result = results[0]
            boxes = getattr(result, "boxes", None)
            names = getattr(result, "names", {}) or {}

            box_count = len(boxes) if boxes else 0
            print(f"✓ Boxes found: {box_count}")

            if boxes and box_count > 0:
                print(f"\nDetections (top 5):")
                for i, box in enumerate(boxes[:5]):
                    class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
                    label = names.get(class_id, f"class_{class_id}")
                    conf = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
                    xyxy = box.xyxy[0].tolist() if getattr(box, "xyxy", None) is not None else []
                    x1, y1, x2, y2 = [f"{x:.0f}" for x in xyxy]
                    print(f"  [{i}] {label:20s} conf={conf:.3f}  bbox=({x1},{y1})-({x2},{y2})")
            else:
                print("No detections (background or threshold too high)")
    except Exception as e:
        print(f"✗ Inference failed: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("="*70)

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "id-card"
    test_model_on_gpu(model)
