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
            err = str(exc)
            # CUDA/cuDNN initialisation errors are permanent for this process —
            # mark the model unavailable so CardDetectorService falls back to
            # classical instead of hitting the same error every frame.
            if any(tag in err for tag in ("cuDNN", "CUBLAS", "CUDA error", "CUDNN_STATUS")):
                self.available = False
                self.status["status"] = "UNAVAILABLE"
                self.status["last_error"] = f"GPU init failed (falling back to classical): {err[:120]}"
                if self.context.logger is not None:
                    self.context.logger.warning(
                        f"YOLO detector disabled due to GPU error — classical fallback active. "
                        f"error={err[:120]}"
                    )
            return CardDetectionResult(
                visible=False,
                status="ERROR",
                error=err,
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

        # Label aliases: models may use different names for business cards
        label_aliases = {
            "visiting_card": self.business_card_label,
            "business_card": self.business_card_label,
            "card": self.business_card_label,
        }

        for box in boxes:
            class_id = int(box.cls[0]) if getattr(box, "cls", None) is not None else -1
            raw_label = names.get(class_id)
            # Map raw model label to canonical business_card label if possible
            label = label_aliases.get(raw_label, raw_label)
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

            # A model without a card class would load fine but never produce a
            # candidate. Accept the configured label OR known aliases (e.g.
            # "visiting_card" for a model trained on business cards).
            model_labels = {str(name) for name in (getattr(self.model, "names", {}) or {}).values()}
            accepted_labels = {self.business_card_label, "visiting_card", "card", "id", "with_id_strap", "without_id_strap"}
            has_card_class = bool(model_labels & accepted_labels)

            if model_labels and not has_card_class:
                self.model = None
                self.status = {
                    "status": "ERROR",
                    "detector": self.detector_name,
                    "model_path": model_path,
                    "last_error": (
                        f"model has no card-like class (looked for: {sorted(accepted_labels)}; "
                        f"found: {sorted(model_labels)[:5]}... total={len(model_labels)})"
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