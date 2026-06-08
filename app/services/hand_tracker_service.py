from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional, Tuple

from app.services.workspace_service import WorkspaceService
from app.cv.hand_tracking import HandMeasurement, HandProxyEstimator, MediaPipeHandDetector


class MediaPipeHandTracker:
    service_name = "hand_tracker"

    def __init__(self, context):
        self.context = context
        hand_config = context.config.get("tracking", {}).get("hand", {})
        self.min_detection_confidence = float(hand_config.get("min_detection_confidence", 0.5))
        self.min_tracking_confidence = float(hand_config.get("min_tracking_confidence", 0.5))
        self.max_proxy_velocity_norm_per_s = float(hand_config.get("max_proxy_velocity_norm_per_s", 2.0))
        self.max_distance_from_card_norm = float(hand_config.get("max_distance_from_card_norm", 0.35))
        self.workspace_margin_px = float(hand_config.get("workspace_margin_px", 20.0))
        self.proxy_estimator = HandProxyEstimator(hand_config.get("fallback_order"))
        self.detector = MediaPipeHandDetector(
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )
        self._last_proxy_norm: Optional[Tuple[float, float]] = None
        self._last_proxy_timestamp: Optional[float] = None

    def detect(self, frame, *, now: Optional[float] = None) -> HandMeasurement:
        timestamp = time.monotonic() if now is None else now
        workspace = self.context.get_service("workspace")
        hand_frame = workspace.transform(frame, workspace_name="hand")
        raw_measurement = self.detector.detect(hand_frame, timestamp=timestamp)
        if not raw_measurement.visible:
            return raw_measurement

        landmark_points = dict(raw_measurement.landmarks)

        proxy_point, proxy_strategy = self.proxy_estimator.estimate(landmark_points)
        if proxy_point is None:
            return HandMeasurement(
                visible=True,
                valid=False,
                confidence=0.2,
                proxy_x=None,
                proxy_y=None,
                proxy_x_normalized=None,
                proxy_y_normalized=None,
                landmarks=landmark_points,
                landmark_measurements=raw_measurement.landmark_measurements,
                source=raw_measurement.source,
                reason="No valid hand proxy could be estimated",
                timestamp=timestamp,
                debug={"proxy_strategy": proxy_strategy},
            )

        card_point = workspace.translate_point(proxy_point, from_workspace="hand", to_workspace="card")
        normalized = workspace.normalize_point(card_point, workspace_name="card")
        validity_reason = self._validate_proxy(landmark_points, card_point, normalized, timestamp, workspace)
        # confidence = raw_measurement.confidence # not used anymore
        valid = validity_reason is None
        if valid:
            self._last_proxy_norm = (normalized["x"], normalized["y"])
            self._last_proxy_timestamp = timestamp

        return HandMeasurement(
            visible=True,
            valid=valid,
            confidence=raw_measurement.confidence,
            proxy_x=card_point[0],
            proxy_y=card_point[1],
            proxy_x_normalized=normalized["x"],
            proxy_y_normalized=normalized["y"],
            landmarks=landmark_points,
            landmark_measurements=raw_measurement.landmark_measurements,
            source=raw_measurement.source,
            reason=validity_reason,
            timestamp=timestamp,
            debug={
                "proxy_strategy": proxy_strategy,
                "card_point": {"x": card_point[0], "y": card_point[1]},
                "normalized": normalized,
            },
        )

    def get_status(self) -> Dict[str, Any]:
        return self.detector.get_status()

    def _validate_proxy(
        self,
        landmarks: Dict[str, Tuple[float, float]],
        card_point: Tuple[float, float],
        normalized: Dict[str, float],
        timestamp: float,
        workspace: WorkspaceService,
    ) -> Optional[str]:
        required = ["index_tip", "middle_tip", "index_pip", "middle_pip"]
        if not all(key in landmarks for key in required):
            return "Missing index/middle finger landmarks"

        finger_distance = math.hypot(
            landmarks["index_tip"][0] - landmarks["middle_tip"][0],
            landmarks["index_tip"][1] - landmarks["middle_tip"][1],
        )
        if finger_distance <= 2.0:
            return "Index/middle finger distance implausibly small"

        if not workspace.contains_point(card_point, workspace_name="card", margin_px=self.workspace_margin_px):
            return "Hand proxy outside card workspace tolerance"

        if self._last_proxy_norm is not None and self._last_proxy_timestamp is not None:
            dt = max(timestamp - self._last_proxy_timestamp, 1e-6)
            velocity = math.hypot(
                normalized["x"] - self._last_proxy_norm[0],
                normalized["y"] - self._last_proxy_norm[1],
            ) / dt
            if velocity > self.max_proxy_velocity_norm_per_s:
                return "Hand proxy velocity exceeded configured limit"

        last_card = self.context.runtime.get("last_card_measurement")
        if last_card is not None and getattr(last_card, "x_normalized", None) is not None:
            if abs(float(last_card.x_normalized) - normalized["x"]) > self.max_distance_from_card_norm:
                return "Hand proxy too far from last card anchor"

        return None