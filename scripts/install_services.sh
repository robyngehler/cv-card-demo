#!/usr/bin/env bash
set -euo pipefail

# Render the systemd unit templates for THIS checkout (path + user are detected
# automatically, with env overrides) and install + enable them. Works whether
# the repo lives in /opt/cv-card-demo or a user home directory.
#
# Overrides:
#   CVD_USER, CVD_GROUP, CVD_DISPLAY, CVD_XAUTHORITY

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$ROOT/systemd"
DST_DIR="/etc/systemd/system"

# When run via sudo, SUDO_USER is the real (non-root) user we want the services
# to run as — not root.
RUN_USER="${CVD_USER:-${SUDO_USER:-$(id -un)}}"
RUN_GROUP="${CVD_GROUP:-$(id -gn "$RUN_USER")}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
RUN_DISPLAY="${CVD_DISPLAY:-${DISPLAY:-:0}}"
RUN_XAUTHORITY="${CVD_XAUTHORITY:-$RUN_HOME/.Xauthority}"

echo "Installing cv-card-demo services"
echo "  root      = $ROOT"
echo "  user      = $RUN_USER"
echo "  group     = $RUN_GROUP"
echo "  display   = $RUN_DISPLAY"
echo "  xauthority= $RUN_XAUTHORITY"

if [ ! -x "$ROOT/scripts/run_backend.sh" ]; then
  chmod +x "$ROOT"/scripts/*.sh || true
fi

render() {
  # render <template.in> <dest-name>
  local template="$1" dest="$2"
  sed \
    -e "s|@ROOT@|$ROOT|g" \
    -e "s|@USER@|$RUN_USER|g" \
    -e "s|@GROUP@|$RUN_GROUP|g" \
    -e "s|@DISPLAY@|$RUN_DISPLAY|g" \
    -e "s|@XAUTHORITY@|$RUN_XAUTHORITY|g" \
    "$SRC_DIR/$template" | sudo tee "$DST_DIR/$dest" >/dev/null
  echo "Installed $dest"
}

# Clean up symlinks from any previous install BEFORE overwriting the unit files.
# `disable` reads the [Install] section of the units currently on disk, so it
# must run while the old files are still present. Earlier versions enabled the
# services directly into multi-user.target / graphical.target, which made
# `disable cv-card-demo.target` ineffective (the services kept autostarting).
# Ignore errors when the units are not yet installed.
sudo systemctl disable cv-card-demo.target cv-card-demo-backend.service cv-card-demo-kiosk.service 2>/dev/null || true

render "cv-card-demo-backend.service.in" "cv-card-demo-backend.service"
render "cv-card-demo-kiosk.service.in" "cv-card-demo-kiosk.service"
sudo cp "$SRC_DIR/cv-card-demo.target" "$DST_DIR/"
echo "Installed cv-card-demo.target"

sudo systemctl daemon-reload
sudo systemctl reset-failed cv-card-demo.target cv-card-demo-backend.service cv-card-demo-kiosk.service 2>/dev/null || true

# Enable ONLY the target into the boot target (multi-user.target). The services
# are bound to the target via WantedBy=cv-card-demo.target (start) + PartOf=
# (stop/restart), so enabling the target is enough for boot autostart, and
# `disable cv-card-demo.target` reliably stops the whole stack from autostarting.
sudo systemctl enable cv-card-demo.target cv-card-demo-backend.service cv-card-demo-kiosk.service

echo
echo "Done. Start now with:"
echo "  sudo systemctl start cv-card-demo.target"
echo "Stop everything with:"
echo "  sudo systemctl stop cv-card-demo.target"
echo "Disable boot autostart with:"
echo "  sudo systemctl disable cv-card-demo.target"
echo "Backend logs:"
echo "  journalctl -u cv-card-demo-backend.service -f"
