#!/usr/bin/env bash
set -euo pipefail

echo "=== CV Card Demo Preflight ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${CV_CARD_DEMO_CONFIG:-$APP_DIR/config/config.yaml}"
VENV_DIR="${CV_CARD_DEMO_VENV:-$APP_DIR/venv}"

echo "[1/9] Checking app directory..."
test -d "$APP_DIR" && echo "OK: $APP_DIR"

echo "[2/9] Checking config..."
test -f "$CONFIG_FILE" && echo "OK: $CONFIG_FILE"

echo "[3/9] Checking Python venv..."
test -d "$VENV_DIR" && echo "OK: $VENV_DIR"

echo "[4/9] Checking Python executable..."
test -x "$VENV_DIR/bin/python" && "$VENV_DIR/bin/python" --version

echo "[5/9] Checking OpenCV import..."
"$VENV_DIR/bin/python" - <<'PY'
import cv2
print("OK: cv2 version:", cv2.__version__)
PY

echo "[6/9] Checking CUDA (torch) with bundled NVIDIA libs..."
NV_LIBS=""
for nv_lib in "$VENV_DIR"/lib/python*/site-packages/nvidia/*/lib; do
  [ -d "$nv_lib" ] && NV_LIBS="${nv_lib}:${NV_LIBS}"
done
LD_LIBRARY_PATH="${NV_LIBS}${LD_LIBRARY_PATH:-}" "$VENV_DIR/bin/python" - <<'PY' || echo "WARN: torch/CUDA check failed (YOLO will fall back to CPU/classical)"
try:
    import torch
    print(f"OK: torch {torch.__version__} cuda_available={torch.cuda.is_available()}")
except Exception as exc:
    print(f"WARN: torch unavailable: {exc}")
PY

echo "[7/9] Checking port 8000..."
if ss -ltn | grep -q ':8000 '; then
  echo "WARN: Port 8000 already in use"
else
  echo "OK: Port 8000 free"
fi

echo "[8/9] Checking video devices..."
if ls /dev/video* >/dev/null 2>&1; then
  ls -l /dev/video*
else
  echo "WARN: No /dev/video* device found"
fi

echo "[9/9] Checking display..."
if [ -n "${DISPLAY:-}" ]; then
  echo "OK: DISPLAY=$DISPLAY"
else
  echo "WARN: DISPLAY is not set"
fi

echo "=== Preflight complete ==="
