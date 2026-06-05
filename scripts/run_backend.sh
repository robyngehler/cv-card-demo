#!/usr/bin/env bash
set -euo pipefail

cd /opt/cv-card-demo

if [ ! -d "/opt/cv-card-demo/venv" ]; then
  echo "ERROR: Python virtual environment not found at /opt/cv-card-demo/venv"
  exit 1
fi

source /opt/cv-card-demo/venv/bin/activate

CONFIG_PATH="${CV_CARD_DEMO_CONFIG:-/opt/cv-card-demo/config/config.yaml}"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "ERROR: Config file not found: $CONFIG_PATH"
  exit 1
fi

exec python -m app.main \
  --config "$CONFIG_PATH" \
  --initial-state BOOT
