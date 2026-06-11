"""Score-to-WLED output adapter.

Mirrors the already-displayed score onto a WLED LED bar:

    displayed_score -> active LED count + color -> POST /json/state -> ESP32

Design rules (see docs/.../cv_card_demo_wled_integration_proposal.md):

- Only the finalized, displayed score drives the LEDs (no second scoring path).
- WLED is optional and non-critical: all network I/O runs on a background worker
  thread, so a slow/absent ESP never blocks tracking, CV, or the UI.
- Updates are rate-limited and de-duplicated to spare WiFi and the ESP.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.wled_client import WledClient


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _lerp_rgb(c0: Tuple[int, int, int], c1: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    t = _clamp(t)
    return (_lerp(c0[0], c1[0], t), _lerp(c0[1], c1[1], t), _lerp(c0[2], c1[2], t))


class WledOutputService:
    service_name = "wled"

    def __init__(self, context):
        self.context = context
        self.logger = getattr(context, "logger", None)
        cfg = (context.config.get("wled", {}) or {})

        self.enabled = bool(cfg.get("enabled", False))
        host = cfg.get("host", "") or ""
        self.led_count = int(cfg.get("led_count", 60))
        self.brightness = int(cfg.get("brightness", 160))
        self.update_hz = float(cfg.get("update_hz", 15.0))
        self.min_interval_s = 1.0 / max(1.0, self.update_hz)
        self.force_refresh_s = float(cfg.get("force_refresh_s", 2.0))
        self.min_leds_when_visible = int(cfg.get("min_leds_when_visible", 1))

        # Segment configuration
        self.segment_id = int(cfg.get("segment_id", 0))
        self.start_led = int(cfg.get("start_led", 0))
        self.stop_led = int(cfg.get("stop_led", self.led_count))
        self.fill_direction = cfg.get("fill_direction", "high_to_low")
        self.preserve_segments = list(cfg.get("preserve_segments", []))

        colors = cfg.get("colors", {}) or {}
        self.low_color = tuple(colors.get("low_rgb", [255, 20, 20]))
        self.mid_color = tuple(colors.get("mid_rgb", [0, 80, 255]))
        self.high_color = tuple(colors.get("high_rgb", [0, 255, 170]))
        idle = cfg.get("idle", {}) or {}
        self.idle_brightness = int(idle.get("brightness", 80))

        self.client = WledClient(
            host,
            endpoint=cfg.get("endpoint", "/json/state"),
            timeout_ms=int(cfg.get("timeout_ms", 300)),
            logger=self.logger,
        )

        # Target the worker should converge on. The caller only sets this; the
        # worker does the rate-limiting, de-duplication, and network I/O.
        self._lock = threading.Lock()
        self._target_score: Optional[float] = None
        self._target_idle: bool = True

        # Observed/applied state (for dedup + health).
        self.status = "OPTIONAL_DISABLED" if not self.enabled else "INIT"
        self.last_score: Optional[float] = None
        self.last_active_leds: Optional[int] = None
        self.last_color: Optional[Tuple[int, int, int]] = None
        self.last_idle: Optional[bool] = None
        self.last_send_ts: float = 0.0          # wall clock, for health age
        self._last_send_monotonic: float = 0.0  # monotonic, for rate limiting

        self._stop = False
        self._worker: Optional[threading.Thread] = None
        if self.enabled and self.client.configured:
            self._worker = threading.Thread(target=self._worker_loop, name="wled-output", daemon=True)
            self._worker.start()
            if self.logger:
                self.logger.info(
                    f"[WLED] output enabled host={self.client.host} "
                    f"segment={self.segment_id} leds={self.start_led}-{self.stop_led} "
                    f"fill={self.fill_direction} update_hz={self.update_hz}"
                )
        elif self.enabled and not self.client.configured:
            self.status = "DEGRADED"
            if self.logger:
                self.logger.warning("[WLED] enabled but no host configured; staying DEGRADED")

    # ---- public API ---------------------------------------------------------

    def update_displayed_score(self, displayed_score: Optional[float]) -> None:
        """Set the target from the same score shown in the UI (None = idle)."""
        if not self.enabled:
            return
        with self._lock:
            if displayed_score is None:
                self._target_idle = True
                self._target_score = None
            else:
                self._target_idle = False
                self._target_score = _clamp(float(displayed_score))

    def set_idle(self) -> None:
        self.update_displayed_score(None)

    def score_to_led_count(self, score: float) -> int:
        active = int(round(_clamp(score) * self.led_count))
        if score > 0.0:
            active = max(self.min_leds_when_visible, active)
        return max(0, min(self.led_count, active))

    def score_to_color(self, score: float) -> Tuple[int, int, int]:
        score = _clamp(score)
        if score <= 0.5:
            return _lerp_rgb(self.low_color, self.mid_color, score / 0.5)
        return _lerp_rgb(self.mid_color, self.high_color, (score - 0.5) / 0.5)

    def _calculate_active_range(self, active: int) -> Tuple[int, int]:
        """Calculate LED range for active LEDs based on fill direction."""
        if self.fill_direction == "high_to_low":
            active_start = max(self.start_led, self.stop_led - active)
            active_stop = self.stop_led
        else:
            active_start = self.start_led
            active_stop = min(self.stop_led, self.start_led + active)
        return (active_start, active_stop)

    def build_payload(self, score: Optional[float], idle: bool) -> Dict[str, Any]:
        """Build WLED /json/state payload.

        Always updates the entire segment range to ensure inactive LEDs are properly
        cleared (prevents color bleed when transitioning from high to low fill).
        """
        if idle or score is None:
            seg = [{"id": self.segment_id, "start": self.start_led, "stop": self.stop_led, "col": [[0, 0, 0]], "fx": 0}]
            return {
                "on": True,
                "bri": self.idle_brightness,
                "seg": seg,
            }

        active = self.score_to_led_count(score)
        color: List[int] = list(self.score_to_color(score))
        seg = []

        if active <= 0:
            seg.append({"id": self.segment_id, "start": self.start_led, "stop": self.stop_led, "col": [[0, 0, 0]], "fx": 0})
        elif active >= self.led_count:
            seg.append({"id": self.segment_id, "start": self.start_led, "stop": self.stop_led, "col": [color], "fx": 0})
        else:
            active_start, active_stop = self._calculate_active_range(active)
            seg.append({"id": self.segment_id, "start": active_start, "stop": active_stop, "col": [color], "fx": 0})
            if active_start > self.start_led:
                seg.append({"id": self.segment_id + 1, "start": self.start_led, "stop": active_start, "col": [[0, 0, 0]], "fx": 0})
            if active_stop < self.stop_led:
                seg.append({"id": self.segment_id + 2, "start": active_stop, "stop": self.stop_led, "col": [[0, 0, 0]], "fx": 0})

        return {"on": True, "bri": self.brightness, "seg": seg}

    def get_status(self) -> Dict[str, Any]:
        age_ms = None
        if self.last_send_ts:
            age_ms = int((time.time() - self.last_send_ts) * 1000)
        return {
            "status": self.status,
            "enabled": self.enabled,
            "host": self.client.host or None,
            "led_count": self.led_count,
            "last_score": self.last_score,
            "last_active_leds": self.last_active_leds,
            "last_color": list(self.last_color) if self.last_color else None,
            "last_update_age_ms": age_ms,
            "last_error": self.client.last_error,
        }

    def is_available(self) -> bool:
        return self.enabled and self.client.configured and self.status == "OK"

    def stop(self) -> None:
        self._stop = True

    # ---- worker -------------------------------------------------------------

    def _worker_loop(self) -> None:
        # Initial reachability probe — informative only, never fatal.
        if self.client.probe():
            self.status = "OK"
            if self.logger:
                self.logger.info("[WLED] probe successful")
        else:
            self.status = "DEGRADED"
            if self.logger:
                self.logger.warning(f"[WLED] probe failed: {self.client.last_error}")

        while not self._stop:
            now = time.monotonic()
            if (now - self._last_send_monotonic) < self.min_interval_s:
                time.sleep(0.01)
                continue

            with self._lock:
                score = self._target_score
                idle = self._target_idle

            if idle or score is None:
                active = 0
                color: Optional[Tuple[int, int, int]] = None
            else:
                active = self.score_to_led_count(score)
                color = self.score_to_color(score)

            forced = (now - self._last_send_monotonic) >= self.force_refresh_s
            changed = (
                idle != self.last_idle
                or active != self.last_active_leds
                or color != self.last_color
            )
            if not (changed or forced):
                time.sleep(self.min_interval_s)
                continue

            payload = self.build_payload(score, idle)
            ok = self.client.post_state(payload)
            self._last_send_monotonic = time.monotonic()
            self.last_send_ts = time.time()
            if ok:
                self.status = "OK"
                self.last_score = score
                self.last_active_leds = active
                self.last_color = color
                self.last_idle = idle
                if self.logger:
                    self.logger.debug(
                        f"[WLED] update score={score} active_leds={active} color={color} idle={idle}"
                    )
            else:
                self.status = "DEGRADED"
                if self.logger:
                    self.logger.warning(f"[WLED] update failed: {self.client.last_error}")

            time.sleep(self.min_interval_s)
