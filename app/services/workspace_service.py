from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple

from app.cv.classical_card_detector import clamp


@dataclass
class ScoreMappingDefinition:
    workspace_name: str = "card"
    axis: str = "x"
    invert: bool = False


@dataclass
class WorkspaceServiceStatus:
    status: str = "NOT_INITIALIZED"
    last_error: Optional[str] = None
    configured_workspaces: list[str] = field(default_factory=list)


@dataclass
class WorkspaceDefinition:
    name: str
    mode: str = "manual_rect"
    source_frame: str = "camera"
    rect_px: Optional[Tuple[int, int, int, int]] = None
    points_px: Optional[Dict[str, Any]] = None
    output_size_px: Optional[Tuple[int, int]] = None
    transform_matrix: Any = None
    inverse_transform_matrix: Any = None
    width: Optional[int] = None
    height: Optional[int] = None


class WorkspaceService:
    def __init__(self, context):
        self.context = context
        self.config: Dict[str, Any] = {}
        self.status = WorkspaceServiceStatus()
        self.score_mapping = ScoreMappingDefinition()
        self.workspaces: Dict[str, WorkspaceDefinition] = {}

    def configure(self, config: Dict[str, Any]) -> None:
        self.config = config or {}
        self.status.status = "VALIDATING"
        card_config = self._workspace_config("card")
        self.score_mapping = ScoreMappingDefinition(
            workspace_name="card",
            axis=card_config.get("score_axis", "x"),
            invert=bool(card_config.get("invert_score_axis", False)),
        )

    def validate(self, frame_shape: Tuple[int, ...]) -> None:
        if not frame_shape or len(frame_shape) < 2:
            self._fail("Invalid frame shape")
            raise ValueError("Invalid frame shape")

        self.workspaces = {}
        for name in self._workspace_names():
            config = self._workspace_config(name)
            definition = WorkspaceDefinition(
                name=name,
                mode=config.get("mode", "manual_rect"),
                source_frame=config.get("source_frame", "camera"),
            )
            if definition.mode == "manual_rect":
                self._validate_manual_rect(definition, config, frame_shape)
            elif definition.mode == "manual_quad":
                self._validate_manual_quad(definition, config, frame_shape)
            else:
                self._fail(f"Unsupported workspace mode: {definition.mode}")
                raise ValueError(f"Unsupported workspace mode: {definition.mode}")

            self.workspaces[name] = definition

        self.status.configured_workspaces = list(self.workspaces.keys())
        self.status.status = "OK"
        self.status.last_error = None

    def transform(self, frame, workspace_name: str = "card"):
        import cv2

        if self.status.status != "OK":
            raise RuntimeError("Workspace is not ready")

        workspace = self._require_workspace(workspace_name)

        if workspace.mode == "manual_rect":
            if workspace.rect_px is None:
                raise RuntimeError(f"Workspace rectangle is not configured for {workspace_name}")
            x, y, width, height = workspace.rect_px
            return frame[y : y + height, x : x + width]

        if workspace.mode == "manual_quad":
            if workspace.transform_matrix is None or workspace.output_size_px is None:
                raise RuntimeError(f"Workspace quad is not configured for {workspace_name}")
            output_width, output_height = workspace.output_size_px
            return cv2.warpPerspective(frame, workspace.transform_matrix, (output_width, output_height))

        raise RuntimeError(f"Unsupported workspace mode: {workspace.mode}")

    def translate_point(
        self,
        point_xy: Tuple[float, float],
        *,
        from_workspace: str,
        to_workspace: str,
    ) -> Tuple[float, float]:
        full_frame_point = self.to_full_frame(point_xy, workspace_name=from_workspace)
        return self.from_full_frame(full_frame_point, workspace_name=to_workspace)

    def to_full_frame(self, point_xy: Tuple[float, float], *, workspace_name: str = "card") -> Tuple[float, float]:
        workspace = self._require_workspace(workspace_name)
        point_x, point_y = float(point_xy[0]), float(point_xy[1])

        if workspace.mode == "manual_rect":
            if workspace.rect_px is None:
                raise RuntimeError(f"Workspace rectangle is not configured for {workspace_name}")
            rect_x, rect_y, _, _ = workspace.rect_px
            return (rect_x + point_x, rect_y + point_y)

        if workspace.mode == "manual_quad":
            if workspace.inverse_transform_matrix is None:
                raise RuntimeError(f"Workspace inverse transform is not configured for {workspace_name}")
            return self._perspective_point((point_x, point_y), workspace.inverse_transform_matrix)

        raise RuntimeError(f"Unsupported workspace mode: {workspace.mode}")

    def from_full_frame(self, point_xy: Tuple[float, float], *, workspace_name: str = "card") -> Tuple[float, float]:
        workspace = self._require_workspace(workspace_name)
        point_x, point_y = float(point_xy[0]), float(point_xy[1])

        if workspace.mode == "manual_rect":
            if workspace.rect_px is None:
                raise RuntimeError(f"Workspace rectangle is not configured for {workspace_name}")
            rect_x, rect_y, _, _ = workspace.rect_px
            return (point_x - rect_x, point_y - rect_y)

        if workspace.mode == "manual_quad":
            if workspace.transform_matrix is None:
                raise RuntimeError(f"Workspace transform is not configured for {workspace_name}")
            return self._perspective_point((point_x, point_y), workspace.transform_matrix)

        raise RuntimeError(f"Unsupported workspace mode: {workspace.mode}")

    def normalize_point(self, point_xy: Tuple[float, float], *, workspace_name: str = "card") -> Dict[str, float]:
        workspace = self._require_workspace(workspace_name)
        if not workspace.width or not workspace.height:
            raise RuntimeError(f"Workspace dimensions are not ready for {workspace_name}")
        return {
            "x": clamp(float(point_xy[0]) / float(max(workspace.width, 1))),
            "y": clamp(float(point_xy[1]) / float(max(workspace.height, 1))),
        }

    def contains_point(
        self,
        point_xy: Tuple[float, float],
        *,
        workspace_name: str = "card",
        margin_px: float = 0.0,
    ) -> bool:
        workspace = self._require_workspace(workspace_name)
        width = float(workspace.width or 0)
        height = float(workspace.height or 0)
        point_x, point_y = float(point_xy[0]), float(point_xy[1])
        return (
            (-margin_px) <= point_x <= (width + margin_px)
            and (-margin_px) <= point_y <= (height + margin_px)
        )

    def get_dimensions(self, workspace_name: str = "card") -> Tuple[int, int]:
        workspace = self._require_workspace(workspace_name)
        if workspace.width is None or workspace.height is None:
            raise RuntimeError(f"Workspace dimensions are not ready for {workspace_name}")
        return (workspace.width, workspace.height)

    def get_status(self) -> Dict[str, Any]:
        payload = asdict(self.status)
        payload["score_mapping"] = asdict(self.score_mapping)
        payload["workspaces"] = {
            name: self._workspace_to_dict(workspace)
            for name, workspace in self.workspaces.items()
        }
        return payload

    def _validate_manual_rect(
        self,
        workspace: WorkspaceDefinition,
        config: Dict[str, Any],
        frame_shape: Tuple[int, ...],
    ) -> None:
        rect = config.get("rect_px", {})
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

        workspace.rect_px = (x, y, width, height)
        workspace.width = width
        workspace.height = height

    def _validate_manual_quad(
        self,
        workspace: WorkspaceDefinition,
        config: Dict[str, Any],
        frame_shape: Tuple[int, ...],
    ) -> None:
        import cv2
        import numpy as np

        points = config.get("points_px", {})
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

        output_size = config.get("output_size_px", {})
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
        workspace.transform_matrix = cv2.getPerspectiveTransform(source_array, destination)
        workspace.inverse_transform_matrix = cv2.getPerspectiveTransform(destination, source_array)
        workspace.output_size_px = (output_width, output_height)
        workspace.width = output_width
        workspace.height = output_height

    def _fail(self, message: str) -> None:
        self.status.status = "ERROR"
        self.status.last_error = message

    def _workspace_names(self) -> list[str]:
        if "card" in self.config or "hand" in self.config:
            names = [name for name in ("card", "hand") if name in self.config]
            return names or ["card"]
        return ["card"]

    def _workspace_config(self, name: str) -> Dict[str, Any]:
        if "card" in self.config or "hand" in self.config:
            return dict(self.config.get(name) or {})
        return dict(self.config) if name == "card" else {}

    def _require_workspace(self, name: str) -> WorkspaceDefinition:
        workspace = self.workspaces.get(name)
        if workspace is None:
            raise RuntimeError(f"Workspace {name!r} is not configured")
        return workspace

    def _workspace_to_dict(self, workspace: WorkspaceDefinition) -> Dict[str, Any]:
        payload = {
            "name": workspace.name,
            "mode": workspace.mode,
            "source_frame": workspace.source_frame,
            "width": workspace.width,
            "height": workspace.height,
        }
        if workspace.rect_px is not None:
            payload["rect_px"] = {
                "x": workspace.rect_px[0],
                "y": workspace.rect_px[1],
                "width": workspace.rect_px[2],
                "height": workspace.rect_px[3],
            }
        if workspace.output_size_px is not None:
            payload["output_size_px"] = {
                "width": workspace.output_size_px[0],
                "height": workspace.output_size_px[1],
            }
        return payload

    def _perspective_point(self, point_xy: Tuple[float, float], matrix) -> Tuple[float, float]:
        import cv2
        import numpy as np

        points = np.array([[[float(point_xy[0]), float(point_xy[1])]]], dtype="float32")
        transformed = cv2.perspectiveTransform(points, matrix)
        return (float(transformed[0][0][0]), float(transformed[0][0][1]))
