"""Low-level WLED JSON-API HTTP client.

Sends state to a WLED device over ``POST /json/state``. Uses only the stdlib
(``urllib``) so the optional LED output adds no dependency. Every call is bounded
by a short timeout and never raises — WLED is decorative and must never block or
crash camera tracking, CV, or the UI.

When the Jetson joins the ESP32's own WLED access point ("WLED-AP"), the device
is reachable at WLED's AP default address ``http://4.3.2.1``.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class WledClient:
    def __init__(
        self,
        host: str,
        *,
        endpoint: str = "/json/state",
        timeout_ms: int = 300,
        logger=None,
    ):
        self.host = (host or "").rstrip("/")
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.timeout_s = max(0.05, float(timeout_ms) / 1000.0)
        self.logger = logger
        self.last_error: Optional[str] = None
        self.last_ok_ts: Optional[float] = None

    @property
    def configured(self) -> bool:
        return bool(self.host)

    def _request(self, path: str, *, data: Optional[bytes] = None, method: str = "GET") -> bool:
        if not self.configured:
            self.last_error = "wled host not configured"
            return False
        url = f"{self.host}{path}"
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                response.read()
            self.last_error = None
            self.last_ok_ts = time.time()
            return True
        except (urllib.error.URLError, OSError, ValueError) as exc:
            # URLError covers timeouts (socket.timeout) and connection refusals.
            self.last_error = str(getattr(exc, "reason", exc))
            return False

    def probe(self) -> bool:
        """Best-effort reachability check via ``GET /json/info``."""
        return self._request("/json/info", method="GET")

    def post_state(self, payload: Dict[str, Any]) -> bool:
        try:
            data = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            self.last_error = f"payload encode failed: {exc}"
            return False
        return self._request(self.endpoint, data=data, method="POST")
