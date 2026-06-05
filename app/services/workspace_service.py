from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class WorkspaceStatus:
    status: str = "NOT_INITIALIZED"
    mode: str = "manual_rect"
    width: Optional[int] = None
    height: Optional[int] = None
    score_axis: str = "x"
    invert_score_axis: bool = False
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkspaceService:
    def __init__(self, context):
        self.context = context
        self.config: Dict[str, Any] = {}
        self.status = WorkspaceStatus()
        self.rect_px: Optional[Tuple[int, int, int, int]] = None
        self.points_px = None
        self.output_size_px: Optional[Tuple[int, int]] = None
        self.transform_matrix = None

    def configure(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.status.status = "VALIDATING"
        self.status.mode = self.config.get("mode", "manual_rect")
        self.status.score_axis = self.config.get("score_axis", "x")
        self.status.invert_score_axis = bool(self.config.get("invert_score_axis", False))

    def validate(self, frame_shape: Tuple[int, ...]) -> None:
        if not frame_shape or len(frame_shape) < 2:
            self._fail("Invalid frame shape")
            raise ValueError("Invalid frame shape")

        mode = self.config.get("mode", "manual_rect")
        if mode == "manual_rect":
            self._validate_manual_rect(frame_shape)
        elif mode == "manual_quad":
            self._validate_manual_quad(frame_shape)
        else:
            self._fail(f"Unsupported workspace mode: {mode}")
            raise ValueError(f"Unsupported workspace mode: {mode}")

        self.status.status = "OK"
        self.status.last_error = None

    def transform(self, frame):
        import cv2

        if self.status.status != "OK":
            raise RuntimeError("Workspace is not ready")

        if self.status.mode == "manual_rect":
            if self.rect_px is None:
                raise RuntimeError("Workspace rectangle is not configured")
            x, y, width, height = self.rect_px
            return frame[y : y + height, x : x + width]

        if self.status.mode == "manual_quad":
            if self.transform_matrix is None or self.output_size_px is None:
                raise RuntimeError("Workspace quad is not configured")
            output_width, output_height = self.output_size_px
            return cv2.warpPerspective(frame, self.transform_matrix, (output_width, output_height))

        raise RuntimeError(f"Unsupported workspace mode: {self.status.mode}")

    def get_status(self) -> Dict[str, Any]:
        payload = asdict(self.status)
        payload.pop("metadata", None)
        if self.rect_px is not None:
            payload["rect_px"] = {
                "x": self.rect_px[0],
                "y": self.rect_px[1],
                "width": self.rect_px[2],
                "height": self.rect_px[3],
            }
        if self.output_size_px is not None:
            payload["output_size_px"] = {
                "width": self.output_size_px[0],
                "height": self.output_size_px[1],
            }
        return payload

    def _validate_manual_rect(self, frame_shape: Tuple[int, ...]) -> None:
        rect = self.config.get("rect_px", {})
        x = int(rect.get("x", 0))
        y = int(rect.get("y", 0))
        width = int(rect.get("width", 0))
        height = int(rect.get("height", 0))

        if width <= 0 or height <= 0:
            self._fail("Workspace rectangle width and height must be positive")
            raise ValueError("Workspace rectangle width and height must be positive")

        frame_height = int(frame_shape[0])
        frame_width = int(frame_shape[1])
        if x < 0 or y < 0 or x + width > frame_width or y + height > frame_height:
            self._fail("Workspace rectangle is outside frame bounds")
            raise ValueError("Workspace rectangle is outside frame bounds")

        self.rect_px = (x, y, width, height)
        self.status.width = width
        self.status.height = height

    def _validate_manual_quad(self, frame_shape: Tuple[int, ...]) -> None:
        import cv2
        import numpy as np

        points = self.config.get("points_px", {})
        required_keys = ["top_left", "top_right", "bottom_right", "bottom_left"]
        try:
            source_points = [points[key] for key in required_keys]
        except KeyError as exc:
            self._fail(f"Missing workspace point: {exc}")
            raise ValueError(f"Missing workspace point: {exc}") from exc

        source_array = np.array(source_points, dtype="float32")
        if source_array.shape != (4, 2):
            self._fail("Workspace quad must contain four 2D points")
            raise ValueError("Workspace quad must contain four 2D points")

        output_size = self.config.get("output_size_px", {})
        output_width = int(output_size.get("width", 0))
        output_height = int(output_size.get("height", 0))
        if output_width <= 0 or output_height <= 0:
            self._fail("Workspace output size must be positive")
            raise ValueError("Workspace output size must be positive")

        frame_height = int(frame_shape[0])
        frame_width = int(frame_shape[1])
        for point_x, point_y in source_array:
            if point_x < 0 or point_y < 0 or point_x > frame_width or point_y > frame_height:
                self._fail("Workspace quad is outside frame bounds")
                raise ValueError("Workspace quad is outside frame bounds")

        destination = np.array(
            [[0, 0], [output_width - 1, 0], [output_width - 1, output_height - 1], [0, output_height - 1]],
            dtype="float32",
        )
        self.transform_matrix = cv2.getPerspectiveTransform(source_array, destination)
        self.output_size_px = (output_width, output_height)
        self.status.width = output_width
        self.status.height = output_height

    def _fail(self, message: str) -> None:
        self.status.status = "ERROR"
        self.status.last_error = message
