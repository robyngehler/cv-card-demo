from __future__ import annotations

from dataclasses import replace
import time
from typing import Any, Dict

from app.cv.classical_card_detector import CardDetectionResult, CardPose, ClassicalCardDetector
from app.cv.yolo_card_detector import YoloCardDetector

class CardDetectorService:
    service_name = "detector"

    def __init__(self, context):
        self.context = context
        self.classical_detector = ClassicalCardDetector(context)
        self.yolo_detector = YoloCardDetector(context)
        self.last_detection_by_state: Dict[str, float] = {}
        self._fallback_warning_emitted = False
        self.cached_result = CardDetectionResult(
            visible=False,
            status="NOT_RUN",
            detector_type="classical_contour",
            primary_label="business_card",
        )

    def detect(self, frame, *, state_name: str = "TRACKING") -> CardDetectionResult:
        workspace = self.context.get_service("workspace")
        workspace_frame = workspace.transform(frame, workspace_name="card")

        if not self._should_run_detection(state_name):
            return self._build_cached_result()

        detector, active_detector, fallback_reason = self._select_detector()
        if detector is None:
            result = CardDetectionResult(
                visible=False,
                status="DETECTOR_UNAVAILABLE",
                error=fallback_reason,
                detector_type="detector_unavailable",
                primary_label=(
                    self.context.config.get("detector", {}).get("business_card_label")
                    or "business_card"
                ),
                debug={
                    "requested_detector": self._requested_detector(),
                    "active_detector": "none",
                    "fallback_reason": fallback_reason,
                },
            )
        else:
            result = detector.detect(workspace_frame)
            result = replace(
                result,
                debug={
                    **dict(result.debug),
                    "requested_detector": self._requested_detector(),
                    "active_detector": active_detector,
                    "fallback_reason": fallback_reason,
                },
            )
        normalized_result = self._normalize_result(result)
        self.cached_result = normalized_result
        self.last_detection_by_state[state_name] = time.monotonic()
        return normalized_result

    def get_status(self) -> Dict[str, Any]:
        detector_status = self._select_detector_status()
        payload = {
            "status": self.cached_result.status,
            "visible": self.cached_result.visible,
            "candidates_count": self.cached_result.candidates_count,
            "detector_type": self.cached_result.detector_type,
            "primary_label": self.cached_result.primary_label,
            "requested_detector": self._requested_detector(),
            "active_detector": self.cached_result.debug.get("active_detector"),
            "fallback_reason": self.cached_result.debug.get("fallback_reason"),
        }
        if self.cached_result.candidate is not None:
            payload["confidence"] = self.cached_result.candidate.confidence
            payload["x_normalized"] = self.cached_result.candidate.x_normalized
        payload.update({"backend": detector_status})
        return payload

    def _select_detector(self):
        detector_type = self._requested_detector()
        if detector_type == "yolo":
            if self.yolo_detector.available:
                return self.yolo_detector, self.yolo_detector.detector_name, None

            fallback_enabled = bool(
                self.context.config.get("detector", {}).get("yolo", {}).get("fallback_to_classical", True)
            )
            fallback_reason = self.yolo_detector.get_status().get("last_error") or "yolo_not_ready"

            if fallback_enabled:
                if not self._fallback_warning_emitted and self.context.logger is not None:
                    self.context.logger.warning(
                        "Detector fallback active: requested=yolo active=classical_contour "
                        f"reason={fallback_reason}"
                    )
                    self._fallback_warning_emitted = True
                return self.classical_detector, self.classical_detector.detector_name, fallback_reason

            return None, "none", fallback_reason

        return self.classical_detector, self.classical_detector.detector_name, None

    def _requested_detector(self) -> str:
        detector_type = str(self.context.config.get("detector", {}).get("type", "classical")).strip().lower()
        return detector_type or "classical"

    def _select_detector_status(self) -> Dict[str, Any]:
        detector_type = self.context.config.get("detector", {}).get("type", "classical")
        if detector_type == "yolo":
            return self.yolo_detector.get_status()
        return self.classical_detector.get_status()

    def _state_frequency_hz(self, state_name: str) -> float:
        frequencies = self.context.config.get("detector", {}).get("loop_hz", {})
        if state_name in frequencies:
            return float(frequencies[state_name])
        return float(frequencies.get("default", 0.0) or 0.0)

    def _should_run_detection(self, state_name: str) -> bool:
        frequency_hz = self._state_frequency_hz(state_name)
        if frequency_hz <= 0.0:
            return True

        now = time.monotonic()
        last_run = self.last_detection_by_state.get(state_name)
        if last_run is None:
            return True

        min_interval = 1.0 / frequency_hz
        return (now - last_run) >= min_interval

    def _normalize_result(self, result: CardDetectionResult) -> CardDetectionResult:
        require_business_card_candidate = bool(
            self.context.config.get("detector", {}).get("require_business_card_candidate", True)
        )
        primary_label = (
            self.context.config.get("detector", {}).get("business_card_label")
            or "business_card"
        )
        normalized_candidates = []
        for candidate in result.candidates:
            normalized_label = candidate.label or primary_label
            normalized_candidates.append(
                replace(
                    candidate,
                    source=candidate.source or result.detector_type,
                    label=normalized_label,
                    is_business_card=bool(candidate.is_business_card and normalized_label == primary_label),
                )
            )

        primary_candidate = result.candidate
        if primary_candidate is not None:
            normalized_label = primary_candidate.label or primary_label
            primary_candidate = replace(
                primary_candidate,
                source=primary_candidate.source or result.detector_type,
                label=normalized_label,
                is_business_card=bool(primary_candidate.is_business_card and normalized_label == primary_label),
            )

        visible = bool(
            primary_candidate is not None
            and (primary_candidate.is_business_card or not require_business_card_candidate)
        )
        return CardDetectionResult(
            visible=visible,
            candidate=primary_candidate if visible else None,
            candidates=normalized_candidates,
            candidates_count=len(normalized_candidates),
            status=result.status,
            debug={
                **dict(result.debug),
                "require_business_card_candidate": require_business_card_candidate,
            },
            error=result.error,
            detector_type=result.detector_type,
            primary_label=primary_label,
            cached=False,
        )

    def _build_cached_result(self) -> CardDetectionResult:
        return CardDetectionResult(
            visible=self.cached_result.visible,
            candidate=self.cached_result.candidate,
            candidates=list(self.cached_result.candidates),
            candidates_count=self.cached_result.candidates_count,
            status=self.cached_result.status,
            debug={**self.cached_result.debug, "cached": True},
            error=self.cached_result.error,
            detector_type=self.cached_result.detector_type,
            primary_label=self.cached_result.primary_label,
            cached=True,
        )