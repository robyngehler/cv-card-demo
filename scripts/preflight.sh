#!/usr/bin/env bash
set -euo pipefail

echo "=== CV Card Demo Preflight ==="

APP_DIR="/opt/cv-card-demo"
CONFIG_FILE="$APP_DIR/config/config.yaml"
VENV_DIR="$APP_DIR/venv"

echo "[1/8] Checking app directory..."
test -d "$APP_DIR" && echo "OK: $APP_DIR"

echo "[2/8] Checking config..."
test -f "$CONFIG_FILE" && echo "OK: $CONFIG_FILE"

echo "[3/8] Checking Python venv..."
test -d "$VENV_DIR" && echo "OK: $VENV_DIR"

echo "[4/8] Checking Python executable..."
test -x "$VENV_DIR/bin/python" && "$VENV_DIR/bin/python" --version

echo "[5/8] Checking OpenCV import..."
"$VENV_DIR/bin/python" - <<'PY'
import cv2
print("OK: cv2 version:", cv2.__version__)
PY

echo "[6/8] Checking port 8000..."
if ss -ltn | grep -q ':8000 '; then
  echo "WARN: Port 8000 already in use"
else
  echo "OK: Port 8000 free"
fi

echo "[7/8] Checking video devices..."
if ls /dev/video* >/dev/null 2>&1; then
  ls -l /dev/video*
else
  echo "WARN: No /dev/video* device found"
fi

echo "[8/8] Checking display..."
if [ -n "${DISPLAY:-}" ]; then
  echo "OK: DISPLAY=$DISPLAY"
else
  echo "WARN: DISPLAY is not set"
fi

echo "=== Preflight complete ==="
