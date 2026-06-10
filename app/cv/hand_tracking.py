from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Any, Dict, Optional, Tuple

import numpy as np


HAND_LANDMARK_NAMES = {
    0: "wrist",
    6: "index_pip",
    8: "index_tip",
    10: "middle_pip",
    12: "middle_tip",
}


@dataclass
class HandLandmarkMeasurement:
    name: str
    x: float
    y: float


@dataclass
class HandMeasurement:
    visible: bool
    valid: bool
    confidence: float
    proxy_x: Optional[float]
    proxy_y: Optional[float]
    proxy_x_normalized: Optional[float]
    proxy_y_normalized: Optional[float]
    landmarks: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    landmark_measurements: Dict[str, HandLandmarkMeasurement] = field(default_factory=dict)
    source: str = "mediapipe_hands"
    reason: Optional[str] = None
    timestamp: float = 0.0
    debug: Dict[str, Any] = field(default_factory=dict)


class HandProxyEstimator:
    def __init__(self, fallback_order: list[str] | None = None):
        self.fallback_order = fallback_order or [
            "index_middle_proxy",
            "index_only_proxy",
            "palm_center_proxy",
        ]

    def estimate(self, landmarks: Dict[str, Tuple[float, float]]) -> tuple[Optional[Tuple[float, float]], str]:
        for strategy in self.fallback_order:
            if strategy == "index_middle_proxy":
                proxy = self._index_middle_proxy(landmarks)
                if proxy is not None:
                    return proxy, strategy
            if strategy == "index_only_proxy":
                proxy = self._index_only_proxy(landmarks)
                if proxy is not None:
                    return proxy, strategy
            if strategy == "palm_center_proxy":
                proxy = self._palm_center_proxy(landmarks)
                if proxy is not None:
                    return proxy, strategy
        return None, "no_proxy"

    def _index_middle_proxy(self, landmarks: Dict[str, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        required = ["index_tip", "middle_tip", "index_pip", "middle_pip"]
        if not all(key in landmarks for key in required):
            return None
        return (
            (0.30 * landmarks["index_tip"][0])
            + (0.30 * landmarks["middle_tip"][0])
            + (0.20 * landmarks["index_pip"][0])
            + (0.20 * landmarks["middle_pip"][0]),
            (0.30 * landmarks["index_tip"][1])
            + (0.30 * landmarks["middle_tip"][1])
            + (0.20 * landmarks["index_pip"][1])
            + (0.20 * landmarks["middle_pip"][1]),
        )

    def _index_only_proxy(self, landmarks: Dict[str, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        required = ["index_tip", "index_pip"]
        if not all(key in landmarks for key in required):
            return None
        return (
            (0.65 * landmarks["index_tip"][0]) + (0.35 * landmarks["index_pip"][0]),
            (0.65 * landmarks["index_tip"][1]) + (0.35 * landmarks["index_pip"][1]),
        )

    def _palm_center_proxy(self, landmarks: Dict[str, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        wrist = landmarks.get("wrist")
        if wrist is None:
            return None
        return wrist


class MediaPipeHandDetector:
    detector_name = "mediapipe_hands"

    def __init__(
        self,
        *,
        min_detection_confidence: float,
        min_tracking_confidence: float,
        model_complexity: int = 0,
        process_max_dim: int = 256,
    ):
        self.min_detection_confidence = float(min_detection_confidence)
        self.min_tracking_confidence = float(min_tracking_confidence)
        # model_complexity 0 = "lite" landmark model (several times faster on
        # CPU than the default full model). Hand tracking only guards snapshots,
        # so the lite model is more than accurate enough.
        self.model_complexity = int(model_complexity)
        # MediaPipe's process() holds the GIL, so a large input stalls the whole
        # process. Downscaling the ROI before process() is the most effective
        # lever for keeping the loop responsive when a hand is present.
        self.process_max_dim = int(process_max_dim)
        self._backend = None
        self._hands = None
        self._status: Dict[str, Any] = {
            "status": "NOT_INITIALIZED",
            "backend": self.detector_name,
        }
        self._load_backend()

    def detect(self, hand_frame, *, timestamp: float) -> HandMeasurement:
        if self._hands is None:
            return HandMeasurement(
                visible=False,
                valid=False,
                confidence=0.0,
                proxy_x=None,
                proxy_y=None,
                proxy_x_normalized=None,
                proxy_y_normalized=None,
                source=self.detector_name,
                reason=self._status.get("last_error") or "MediaPipe backend unavailable",
                timestamp=timestamp,
                debug={"status": self._status.get("status")},
            )

        # Downscale a copy for MediaPipe; landmarks come back normalised, so we
        # still scale them against the original ROI dimensions below.
        rgb = hand_frame[:, :, ::-1]
        max_dim = max(int(hand_frame.shape[0]), int(hand_frame.shape[1]))
        if self.process_max_dim > 0 and max_dim > self.process_max_dim:
            scale = self.process_max_dim / float(max_dim)
            try:
                import cv2 as _cv2
                rgb = _cv2.resize(
                    rgb,
                    (max(1, int(hand_frame.shape[1] * scale)), max(1, int(hand_frame.shape[0] * scale))),
                    interpolation=_cv2.INTER_AREA,
                )
            except Exception:
                rgb = hand_frame[:, :, ::-1]
        rgb = np.ascontiguousarray(rgb)

        try:
            results = self._hands.process(rgb)
        except Exception as exc:
            self._status["status"] = "ERROR"
            self._status["last_error"] = str(exc)
            return HandMeasurement(
                visible=False,
                valid=False,
                confidence=0.0,
                proxy_x=None,
                proxy_y=None,
                proxy_x_normalized=None,
                proxy_y_normalized=None,
                source=self.detector_name,
                reason=str(exc),
                timestamp=timestamp,
            )

        multi_hand_landmarks = getattr(results, "multi_hand_landmarks", None)
        if not multi_hand_landmarks:
            return HandMeasurement(
                visible=False,
                valid=False,
                confidence=0.0,
                proxy_x=None,
                proxy_y=None,
                proxy_x_normalized=None,
                proxy_y_normalized=None,
                source=self.detector_name,
                reason="No hand landmarks detected",
                timestamp=timestamp,
            )

        selected_landmarks = multi_hand_landmarks[0]
        frame_height = int(hand_frame.shape[0])
        frame_width = int(hand_frame.shape[1])
        landmark_points: Dict[str, Tuple[float, float]] = {}
        landmark_measurements: Dict[str, HandLandmarkMeasurement] = {}
        for index, landmark in enumerate(selected_landmarks.landmark):
            landmark_name = HAND_LANDMARK_NAMES.get(index)
            if landmark_name is None:
                continue
            point = (
                float(landmark.x) * float(frame_width),
                float(landmark.y) * float(frame_height),
            )
            landmark_points[landmark_name] = point
            landmark_measurements[landmark_name] = HandLandmarkMeasurement(
                name=landmark_name,
                x=point[0],
                y=point[1],
            )

        confidence = self._extract_handedness_confidence(results)
        return HandMeasurement(
            visible=True,
            valid=False,
            confidence=confidence,
            proxy_x=None,
            proxy_y=None,
            proxy_x_normalized=None,
            proxy_y_normalized=None,
            landmarks=landmark_points,
            landmark_measurements=landmark_measurements,
            source=self.detector_name,
            timestamp=timestamp,
        )

    def get_status(self) -> Dict[str, Any]:
        return dict(self._status)

    def _load_backend(self) -> None:
        import os
        # Suppress TFLite / glog stderr spam that floods the terminal when hands appear.
        os.environ.setdefault("GLOG_minloglevel", "2")
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")
        try:
            mp = importlib.import_module("mediapipe")
        except Exception as exc:
            self._status = {
                "status": "UNAVAILABLE",
                "backend": self.detector_name,
                "last_error": str(exc),
            }
            return

        self._backend = mp
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=self.model_complexity,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )
        self._status = {
            "status": "READY",
            "backend": self.detector_name,
            "model_complexity": self.model_complexity,
            "process_max_dim": self.process_max_dim,
        }

    @staticmethod
    def _extract_handedness_confidence(results) -> float:
        handedness = getattr(results, "multi_handedness", None)
        if handedness and handedness[0].classification:
            return float(handedness[0].classification[0].score)
        return 0.75