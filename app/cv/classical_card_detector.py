from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class CardPose:
    visible: bool
    x: float
    y: float
    theta_deg: float
    width: float
    height: float
    confidence: float
    x_normalized: Optional[float] = None
    y_normalized: Optional[float] = None
    source: str = "classical_contour"
    label: str = "business_card"
    is_business_card: bool = True
    bbox_points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class CardDetectionResult:
    visible: bool
    candidate: Optional[CardPose] = None
    candidates: list[CardPose] = field(default_factory=list)
    candidates_count: int = 0
    status: str = "OK"
    debug: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    detector_type: str = "classical_contour"
    primary_label: Optional[str] = "business_card"
    cached: bool = False


class ClassicalCardDetector:
    def __init__(self, context):
        self.context = context
        self.detector_name = "classical_contour"
        self.business_card_label = (
            context.config.get("detector", {}).get("business_card_label")
            or "business_card"
        )
        self.status: Dict[str, Any] = {
            "status": "NOT_INITIALIZED",
            "visible": False,
            "candidates_count": 0,
            "confidence": 0.0,
            "x_normalized": None,
        }

    def detect(self, workspace_frame) -> CardDetectionResult:
        try:
            import cv2
        except ImportError as exc:
            self._update_status("ERROR", error="OpenCV is not available")
            return CardDetectionResult(
                visible=False,
                status="ERROR",
                error="OpenCV is not available",
                detector_type="classical_contour",
            )

        if workspace_frame is None or len(workspace_frame.shape) < 2:
            self._update_status("ERROR", error="Invalid workspace frame")
            return CardDetectionResult(
                visible=False,
                status="ERROR",
                error="Invalid workspace frame",
                detector_type="classical_contour",
            )

        config = self.context.config.get("detector", {})
        preprocessing = config.get("preprocessing", {})
        contour_filter = config.get("contour_filter", {})
        confidence_cfg = config.get("confidence", {})

        grayscale = bool(preprocessing.get("grayscale", True))
        blur_kernel = int(preprocessing.get("blur_kernel", 5))
        threshold_mode = preprocessing.get("threshold_mode", "adaptive")
        canny_enabled = bool(preprocessing.get("canny_enabled", False))
        morphology_enabled = bool(preprocessing.get("morphology_enabled", True))
        morphology_kernel_size = max(1, int(preprocessing.get("morphology_kernel_size", 3)))
        morphology_close_iterations = max(0, int(preprocessing.get("morphology_close_iterations", 2)))
        morphology_open_iterations = max(0, int(preprocessing.get("morphology_open_iterations", 1)))

        min_area_px = int(contour_filter.get("min_area_px", 1000))
        max_area_ratio = float(contour_filter.get("max_area_ratio", 0.8))
        min_aspect_ratio = float(contour_filter.get("min_aspect_ratio", 1.2))
        max_aspect_ratio = float(contour_filter.get("max_aspect_ratio", 2.2))
        min_confidence = float(confidence_cfg.get("min_confidence", 0.5))
        expected_card_area_px = float(confidence_cfg.get("expected_card_area_px", 3200.0))
        target_aspect_ratio = float(confidence_cfg.get("target_aspect_ratio", 1.65))
        aspect_tolerance = max(0.01, float(confidence_cfg.get("aspect_tolerance", 0.55)))
        weight_area = float(confidence_cfg.get("weight_area", 0.35))
        weight_aspect = float(confidence_cfg.get("weight_aspect", 0.35))
        weight_rectangularity = float(confidence_cfg.get("weight_rectangularity", 0.30))

        frame = workspace_frame
        if grayscale and len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if blur_kernel > 1:
            if blur_kernel % 2 == 0:
                blur_kernel += 1
            frame = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

        if canny_enabled:
            edges = cv2.Canny(frame, 50, 150)
            mask = edges
        elif threshold_mode == "otsu":
            _, mask = cv2.threshold(frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            mask = cv2.adaptiveThreshold(
                frame,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                31,
                5,
            )

        if morphology_enabled:
            if morphology_kernel_size % 2 == 0:
                morphology_kernel_size += 1
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (morphology_kernel_size, morphology_kernel_size),
            )
            if morphology_close_iterations > 0:
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=morphology_close_iterations)
            if morphology_open_iterations > 0:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=morphology_open_iterations)

        contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

        frame_area = float(mask.shape[0] * mask.shape[1])
        candidates = []
        debug_contours = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area_px or area > frame_area * max_area_ratio:
                continue

            rect = cv2.minAreaRect(contour)
            (center_x, center_y), (width, height), theta_deg = rect
            if width <= 0 or height <= 0:
                continue

            aspect_ratio = max(width, height) / min(width, height)
            if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio:
                continue

            rect_area = float(width * height)
            if rect_area <= 0.0:
                continue

            area_score = clamp(area / expected_card_area_px)
            aspect_score = clamp(1.0 - (abs(aspect_ratio - target_aspect_ratio) / aspect_tolerance))
            rectangularity_score = clamp(area / rect_area)
            confidence = clamp(
                (weight_area * area_score)
                + (weight_aspect * aspect_score)
                + (weight_rectangularity * rectangularity_score)
            )
            if confidence < min_confidence:
                continue

            x_normalized = clamp(float(center_x) / float(mask.shape[1]))
            y_normalized = clamp(float(center_y) / float(mask.shape[0]))
            box_points = cv2.boxPoints(rect)
            pose = CardPose(
                visible=True,
                x=float(center_x),
                y=float(center_y),
                theta_deg=float(theta_deg),
                width=float(width),
                height=float(height),
                confidence=confidence,
                x_normalized=x_normalized,
                y_normalized=y_normalized,
                source=self.detector_name,
                label=self.business_card_label,
                is_business_card=True,
                bbox_points=[(float(x), float(y)) for x, y in box_points],
            )
            candidates.append(pose)
            debug_contours.append(
                {
                    "area": area,
                    "aspect_ratio": aspect_ratio,
                    "rectangularity": rectangularity_score,
                    "confidence": confidence,
                }
            )

        if candidates:
            best_candidate = max(candidates, key=lambda pose: pose.confidence)
            self._update_status(
                "OK",
                visible=True,
                candidates_count=len(candidates),
                confidence=best_candidate.confidence,
                x_normalized=best_candidate.x_normalized,
            )
            return CardDetectionResult(
                visible=True,
                candidate=best_candidate,
                candidates=sorted(candidates, key=lambda pose: pose.confidence, reverse=True),
                candidates_count=len(candidates),
                status="OK",
                debug={"contours": debug_contours},
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
            )

        self._update_status("OK", visible=False, candidates_count=0, confidence=0.0, x_normalized=None)
        return CardDetectionResult(
            visible=False,
            candidate=None,
            candidates=[],
            candidates_count=0,
            status="OK",
            debug={"contours": debug_contours},
            detector_type=self.detector_name,
            primary_label=self.business_card_label,
        )

    def get_status(self) -> Dict[str, Any]:
        return dict(self.status)

    def draw_debug(self, workspace_frame, result: CardDetectionResult, mask=None, preprocessed_frame=None):
        """
        Draw debug overlays on the workspace frame.
        Returns a 3-channel BGR image suitable for cv2.imshow.
        """
        import cv2

        frame = workspace_frame.copy()
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        if result.visible and result.candidate:
            candidate = result.candidate
            center = (int(candidate.x), int(candidate.y))
            cv2.circle(frame, center, 5, (0, 255, 0), -1)
            angle = -candidate.theta_deg
            size = (int(candidate.width), int(candidate.height))
            box = cv2.boxPoints(((candidate.x, candidate.y), size, angle))
            box = box.astype(int)
            cv2.polylines(frame, [box], True, (0, 255, 0), 2)
            text = (
                f"CARD: conf={candidate.confidence:.2f} "
                f"x_norm={candidate.x_normalized:.2f}"
            )
            cv2.putText(
                frame,
                text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
        else:
            text = f"NO CARD: candidates={result.candidates_count}"
            cv2.putText(
                frame,
                text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
            )

        return frame

    def _update_status(
        self,
        status: str,
        *,
        visible: bool,
        candidates_count: int,
        confidence: float,
        x_normalized: Optional[float],
        error: Optional[str] = None,
    ) -> None:
        self.status.update(
            {
                "status": status,
                "visible": visible,
                "candidates_count": candidates_count,
                "confidence": confidence,
                "x_normalized": x_normalized,
            }
        )
        if error is not None:
            self.status["last_error"] = error
