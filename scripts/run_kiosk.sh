#!/usr/bin/env bash
set -euo pipefail

URL="${CV_CARD_DEMO_URL:-http://localhost:8000}"

# Wait for the backend to answer health before opening the browser.
for _ in {1..40}; do
  if curl -fsS "$URL/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if command -v chromium-browser >/dev/null 2>&1; then
  BROWSER="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
  BROWSER="chromium"
elif command -v google-chrome >/dev/null 2>&1; then
  BROWSER="google-chrome"
else
  echo "ERROR: No supported browser found (chromium-browser/chromium/google-chrome)." >&2
  exit 1
fi

exec "$BROWSER" \
  --kiosk "$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000
