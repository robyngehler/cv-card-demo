#!/bin/bash
# Test YOLO models using a running backend for GPU context.
# Start backend first, then run this script to test models.

set -e

MODEL_NAME="${1:-visiting_card}"
BACKEND_URL="${2:-http://localhost:8000}"

echo "=========================================================================="
echo "YOLO MODEL INFERENCE TEST (via Backend API)"
echo "=========================================================================="
echo "Model: $MODEL_NAME"
echo "Backend: $BACKEND_URL"
echo ""

# Check backend is running
if ! curl -s "$BACKEND_URL/api/health" > /dev/null 2>&1; then
    echo "ERROR: Backend not responding at $BACKEND_URL"
    echo "Start backend first: ./scripts/run_backend.sh"
    exit 1
fi

echo "✓ Backend is ready"
echo ""

# Export CUDA libs (same as run_backend.sh)
for nv in venv/lib/python*/site-packages/nvidia/*/lib; do
    if [ -d "$nv" ]; then
        export LD_LIBRARY_PATH="$nv:${LD_LIBRARY_PATH:-}"
    fi
done

PYTHONPATH=/home/aiuser/workspace/cv-card-demo venv/bin/python3 - <<PYEOF
import requests
import numpy as np
import cv2
from ultralytics import YOLO
import torch

# Ensure CUDA is initialized
torch.cuda.is_available()
torch.cuda.init()

print("CUDA available:", torch.cuda.is_available())
print()

# Grab frame from backend
print("Fetching frame from backend API...")
response = requests.get("${BACKEND_URL}/api/live-frame?mode=run", timeout=5)
frame = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
print(f"Frame shape: {frame.shape}")
print()

# Model paths
models = {
    "visiting_card": "models/yolov8_visiting_card.pt",
    "id-card": "models/YOLO-id-card.pt",
}

model_path = models.get("${MODEL_NAME}")
if not model_path:
    print(f"Unknown model: ${MODEL_NAME}")
    exit(1)

print(f"Loading {model_path}...")
model = YOLO(model_path)
print(f"Device: {model.device}")
print()

# Run inference with different thresholds
for conf_threshold in [0.25, 0.5, 0.75]:
    print(f"Inference with conf={conf_threshold}:")
    try:
        results = model.predict(source=frame, verbose=False, conf=conf_threshold)

        if results:
            result = results[0]
            boxes = getattr(result, "boxes", None)
            names = getattr(result, "names", {}) or {}

            box_count = len(boxes) if boxes else 0
            print(f"  Boxes found: {box_count}")

            if boxes and box_count > 0:
                for i, box in enumerate(boxes[:3]):
                    class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
                    label = names.get(class_id, f"class_{class_id}")
                    conf = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
                    xyxy = box.xyxy[0].tolist() if getattr(box, "xyxy", None) is not None else []
                    print(f"    [{i}] {label} conf={conf:.3f} bbox={[f'{x:.0f}' for x in xyxy]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

print("========================================================================")
print("✓ Test complete")
print("========================================================================")
PYEOF
