#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)/../systemd"
DST_DIR="/etc/systemd/system"

for unit in cv-card-demo.target cv-card-demo-backend.service cv-card-demo-kiosk.service; do
  sudo cp "$SRC_DIR/$unit" "$DST_DIR/"
  echo "Installed $unit"
done

sudo systemctl daemon-reload
sudo systemctl enable cv-card-demo.target

echo "Installed and enabled cv-card-demo.target"
