#!/usr/bin/env bash
set -euo pipefail

# Resolve the repository root from this script's location so the launcher works
# regardless of where the repo lives (e.g. /opt/cv-card-demo or ~/workspace/...).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT"

VENV_DIR="${CV_CARD_DEMO_VENV:-$ROOT/venv}"
if [ ! -d "$VENV_DIR" ]; then
  echo "ERROR: Python virtual environment not found at $VENV_DIR" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Make the bundled NVIDIA CUDA user libraries (libcudss, cuBLAS, cuDNN, …)
# discoverable so torch/ultralytics can initialise CUDA. Without this the YOLO
# detector fails to import ("libcudss.so.0: cannot open shared object file")
# and silently falls back to the slower classical contour detector.
for nv_lib in "${VIRTUAL_ENV}"/lib/python*/site-packages/nvidia/*/lib; do
  if [ -d "$nv_lib" ]; then
    LD_LIBRARY_PATH="${nv_lib}:${LD_LIBRARY_PATH:-}"
  fi
done
export LD_LIBRARY_PATH

CONFIG_PATH="${CV_CARD_DEMO_CONFIG:-$ROOT/config/config.yaml}"
if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: Config file not found: $CONFIG_PATH" >&2
  exit 1
fi

exec python -m app.main \
  --config "$CONFIG_PATH" \
  --initial-state BOOT
