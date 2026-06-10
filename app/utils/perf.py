"""Lightweight, always-on timing instrumentation.

The booth shows a steady 20-40 Hz tracking rate with periodic latency spikes.
To find which stage spikes (and confirm YOLO / MediaPipe stay off the critical
path) we record per-stage durations and log an aggregate (median / p95 / max)
every few seconds. This is cheap: a dict of lists guarded by a lock, aggregated
and cleared on each periodic flush.

Usage:

    perf = PerfMonitor(logger)
    with perf.span("card_detect"):
        result = detector.detect(frame)
    ...
    perf.maybe_log("TRACKING")   # self-throttles to log_interval_s
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = pct / 100.0 * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


class PerfMonitor:
    def __init__(self, logger=None, *, log_interval_s: float = 5.0, spike_warn_ms: float = 80.0):
        self.logger = logger
        self.log_interval_s = float(log_interval_s)
        self.spike_warn_ms = float(spike_warn_ms)
        self._lock = threading.Lock()
        self._samples: Dict[str, List[float]] = {}
        self._last_flush = time.monotonic()
        # Aggregates from the most recent flush, exposed via get_status().
        self._last_report: Dict[str, Any] = {}
        self._last_report_ts: float = 0.0

    # Hard cap on per-stage samples between flushes so memory stays bounded even
    # if maybe_log() is not called for a long time (e.g. while idle).
    _MAX_SAMPLES_PER_STAGE = 5000

    def record(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            bucket = self._samples.setdefault(stage, [])
            if len(bucket) < self._MAX_SAMPLES_PER_STAGE:
                bucket.append(float(duration_ms))

    @contextmanager
    def span(self, stage: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(stage, (time.perf_counter() - start) * 1000.0)

    def maybe_log(self, prefix: str = "") -> None:
        """Emit an aggregate line if log_interval_s has elapsed (else no-op)."""
        now = time.monotonic()
        if (now - self._last_flush) < self.log_interval_s:
            return
        with self._lock:
            samples = self._samples
            self._samples = {}
            window_s = now - self._last_flush
            self._last_flush = now

        if not samples:
            return

        report: Dict[str, Any] = {"window_s": round(window_s, 1), "stages": {}}
        worst_stage = None
        worst_max = 0.0
        parts = []
        for stage, values in samples.items():
            values.sort()
            count = len(values)
            p50 = _percentile(values, 50.0)
            p95 = _percentile(values, 95.0)
            vmax = values[-1]
            report["stages"][stage] = {
                "count": count,
                "p50_ms": round(p50, 1),
                "p95_ms": round(p95, 1),
                "max_ms": round(vmax, 1),
            }
            parts.append(f"{stage}[n={count} p50={p50:.0f} p95={p95:.0f} max={vmax:.0f}]")
            if vmax > worst_max:
                worst_max = vmax
                worst_stage = stage

        report["worst_stage"] = worst_stage
        report["worst_max_ms"] = round(worst_max, 1)
        self._last_report = report
        self._last_report_ts = time.time()

        if self.logger is not None:
            line = f"PERF {prefix} " + " ".join(parts)
            if worst_max >= self.spike_warn_ms:
                self.logger.warning(line + f" SPIKE worst={worst_stage}={worst_max:.0f}ms")
            else:
                self.logger.info(line)

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "OK",
            "log_interval_s": self.log_interval_s,
            "report_age_s": round(time.time() - self._last_report_ts, 1) if self._last_report_ts else None,
            "last_report": self._last_report,
        }
