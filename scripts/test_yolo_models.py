#!/usr/bin/env python3
"""
Quick test: load both YOLO models, inspect labels, and optionally run inference.
Run with a live card in the workspace for quick feedback.
"""
import sys
import time
import cv2
from pathlib import Path

def test_model_labels():
    """Load models and show what labels they have."""
    import torch

    models = {
        "visiting_card": "models/yolov8_visiting_card.pt",
        "id-card": "models/YOLO-id-card.pt",
    }

    print("\n" + "=" * 70)
    print("YOLO MODEL LABELS")
    print("=" * 70)

    for name, path in models.items():
        print(f"\n[{name.upper()}] {path}")
        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            m = getattr(ckpt, "model", ckpt.get("model") if isinstance(ckpt, dict) else None)
            names = getattr(m, "names", {}) if m else ckpt.get("names", {})

            print(f"  Classes ({len(names)}): {list(names.values())}")

            # Check for usable labels
            usable = [v for v in names.values() if v.lower() in ['visiting_card', 'card', 'id', 'with_id_strap', 'without_id_strap']]
            if usable:
                print(f"  ✓ Usable labels: {usable}")
            else:
                print(f"  ✗ No 'visiting_card' / 'card' / 'id' label found")

        except Exception as e:
            print(f"  ERROR: {e}")


def test_model_inference(model_name: str = "visiting_card", conf: float = 0.25):
    """Run inference on a single camera frame."""
    from ultralytics import YOLO

    model_path = {
        "visiting_card": "models/yolov8_visiting_card.pt",
        "id-card": "models/YOLO-id-card.pt",
    }.get(model_name)

    if not model_path:
        print(f"Unknown model: {model_name}")
        return

    print(f"\n[INFERENCE TEST] Loading {model_name}...")
    try:
        model = YOLO(model_path)
        print(f"✓ Model loaded. Device: {model.device}")
    except Exception as e:
        print(f"✗ Failed to load: {e}")
        return

    # Grab a frame from the camera
    print("Waiting for camera frame...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    time.sleep(0.5)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("✗ Could not read camera frame")
        return

    print(f"Frame shape: {frame.shape}")

    # Run inference
    print(f"Running inference with conf={conf}...")
    start = time.monotonic()
    results = model.predict(source=frame, verbose=False, conf=conf)
    elapsed = time.monotonic() - start
    print(f"Inference time: {elapsed*1000:.1f} ms")

    if not results:
        print("✗ No results")
        return

    result = results[0]
    boxes = getattr(result, "boxes", None)
    names = getattr(result, "names", {}) or {}

    print(f"\nResults:")
    print(f"  Boxes detected: {len(boxes) if boxes else 0}")

    if boxes:
        for i, box in enumerate(boxes):
            class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
            label = names.get(class_id, f"class_{class_id}")
            conf_val = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            xyxy = box.xyxy[0].tolist() if getattr(box, "xyxy", None) is not None else []
            print(f"    [{i}] {label} conf={conf_val:.2f} bbox={[f'{x:.0f}' for x in xyxy]}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "infer":
        model = sys.argv[2] if len(sys.argv) > 2 else "id-card"
        test_model_inference(model)
    else:
        test_model_labels()
        print("\nRun `python scripts/test_yolo_models.py infer [visiting_card|id-card]` to test inference.")
