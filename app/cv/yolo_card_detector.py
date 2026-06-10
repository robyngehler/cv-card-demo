from __future__ import annotations

import importlib
from typing import Any, Dict

from app.cv.classical_card_detector import CardDetectionResult, CardPose


class YoloCardDetector:
    detector_name = "yolo_business_card"

    def __init__(self, context):
        self.context = context
        self.model = None
        self.available = False
        self.status: Dict[str, Any] = {
            "status": "NOT_CONFIGURED",
            "detector": self.detector_name,
        }
        self.business_card_label = (
            context.config.get("detector", {}).get("business_card_label")
            or "business_card"
        )
        self.device = "cpu"
        self._load_model()

    def detect(self, workspace_frame) -> CardDetectionResult:
        if not self.available or self.model is None:
            return CardDetectionResult(
                visible=False,
                status=self.status.get("status", "UNAVAILABLE"),
                error=self.status.get("last_error"),
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
            )

        conf_threshold = float(
            self.context.config.get("detector", {}).get("yolo", {}).get("confidence", 0.25)
        )

        try:
            results = self.model.predict(
                source=workspace_frame, verbose=False, conf=conf_threshold, device=self.device
            )
        except Exception as exc:
            return CardDetectionResult(
                visible=False,
                status="ERROR",
                error=str(exc),
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
            )

        if not results:
            return CardDetectionResult(
                visible=False,
                status="OK",
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
            )

        first_result = results[0]
        names = getattr(first_result, "names", {}) or {}
        boxes = getattr(first_result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return CardDetectionResult(
                visible=False,
                status="OK",
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
            )

        candidates: list[CardPose] = []
        frame_height = int(workspace_frame.shape[0])
        frame_width = int(workspace_frame.shape[1])
        for box in boxes:
            class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
            label = names.get(class_id)
            if label != self.business_card_label:
                continue

            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [float(value) for value in xyxy]
            width = max(0.0, x2 - x1)
            height = max(0.0, y2 - y1)
            center_x = x1 + (width / 2.0)
            center_y = y1 + (height / 2.0)
            confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            candidates.append(
                CardPose(
                    visible=True,
                    x=center_x,
                    y=center_y,
                    theta_deg=0.0,
                    width=width,
                    height=height,
                    confidence=confidence,
                    x_normalized=max(0.0, min(1.0, center_x / float(max(frame_width, 1)))),
                    y_normalized=max(0.0, min(1.0, center_y / float(max(frame_height, 1)))),
                    source=self.detector_name,
                    label=label,
                    is_business_card=True,
                    bbox_points=[
                        (x1, y1),
                        (x2, y1),
                        (x2, y2),
                        (x1, y2),
                    ],
                )
            )

        if not candidates:
            return CardDetectionResult(
                visible=False,
                status="OK",
                detector_type=self.detector_name,
                primary_label=self.business_card_label,
                debug={"reason": "No business_card class detected"},
            )

        best_candidate = max(candidates, key=lambda candidate: candidate.confidence)
        return CardDetectionResult(
            visible=True,
            candidate=best_candidate,
            candidates=sorted(candidates, key=lambda candidate: candidate.confidence, reverse=True),
            candidates_count=len(candidates),
            status="OK",
            detector_type=self.detector_name,
            primary_label=self.business_card_label,
            debug={"source": self.detector_name},
        )

    def get_status(self) -> Dict[str, Any]:
        return dict(self.status)

    def _load_model(self) -> None:
        detector_config = self.context.config.get("detector", {})
        yolo_config = detector_config.get("yolo", {})
        model_path = yolo_config.get("model_path")
        if not model_path:
            self.status["status"] = "NOT_CONFIGURED"
            return

        try:
            ultralytics_module = importlib.import_module("ultralytics")
            yolo_class = getattr(ultralytics_module, "YOLO")
        except Exception as exc:
            self.status = {
                "status": "UNAVAILABLE",
                "detector": self.detector_name,
                "last_error": str(exc),
            }
            return

        try:
            self.model = yolo_class(model_path)

            # A model without the configured card class (e.g. stock COCO
            # weights) would load fine but never produce a candidate. Treat it
            # as unavailable so CardDetectorService falls back to classical
            # with a visible warning instead of failing silently.
            model_labels = {str(name) for name in (getattr(self.model, "names", {}) or {}).values()}
            if model_labels and self.business_card_label not in model_labels:
                self.model = None
                self.status = {
                    "status": "ERROR",
                    "detector": self.detector_name,
                    "model_path": model_path,
                    "last_error": (
                        f"model has no class '{self.business_card_label}' "
                        f"(model classes: {sorted(model_labels)[:5]}... total={len(model_labels)})"
                    ),
                }
                if self.context.logger is not None:
                    self.context.logger.warning(
                        f"YOLO detector disabled: {self.status['last_error']} model={model_path}"
                    )
                return

            self.device = self._select_device(yolo_config)
            if self.device != "cpu":
                try:
                    self.model.to(self.device)
                except Exception:
                    # Keep the model usable on CPU if the move fails.
                    self.device = "cpu"
            self.available = True
            self.status = {
                "status": "READY",
                "detector": self.detector_name,
                "model_path": model_path,
                "device": self.device,
            }
            if self.context.logger is not None:
                self.context.logger.info(
                    f"YOLO detector ready model={model_path} device={self.device}"
                )
        except Exception as exc:
            self.status = {
                "status": "ERROR",
                "detector": self.detector_name,
                "last_error": str(exc),
            }

    def _select_device(self, yolo_config: Dict[str, Any]) -> str:
        configured = str(yolo_config.get("device", "auto")).strip().lower()
        if configured not in ("", "auto"):
            return configured
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda:0"
        except Exception as exc:
            if self.context.logger is not None:
                self.context.logger.warning(
                    f"YOLO detector: CUDA unavailable, using CPU (reason={exc})"
                )
        return "cpu"