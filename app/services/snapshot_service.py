from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional

import cv2


@dataclass
class SnapshotRecord:
    snapshot_id: str
    candidate_id: Optional[str]
    session_id: Optional[str]
    question_id: Optional[str]
    image_path: str
    crop_path: Optional[str]
    created_at: str


class SnapshotService:
    service_name = "snapshot"

    def __init__(self, context):
        self.context = context
        snapshot_config = context.config.get("snapshot", {})
        self.output_dir = Path(snapshot_config.get("output_dir", "./data/snapshots"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.status: Dict[str, Any] = {
            "status": "READY",
            "output_dir": str(self.output_dir),
        }

    def capture(
        self,
        *,
        frame,
        card_measurement,
        session_id: Optional[str],
        candidate_id: Optional[str],
        question_id: Optional[str],
    ) -> SnapshotRecord:
        return self._write_snapshot(
            frame=frame,
            card_measurement=card_measurement,
            session_id=session_id,
            candidate_id=candidate_id,
            question_id=question_id,
            prefix="snapshot",
        )

    def capture_preview(self, *, frame, card_measurement) -> SnapshotRecord:
        return self._write_snapshot(
            frame=frame,
            card_measurement=card_measurement,
            session_id=None,
            candidate_id=None,
            question_id=None,
            prefix="precheck",
        )

    def enqueue_processing(self, snapshot_record: SnapshotRecord) -> None:
        processor = self.context.get_service("snapshot_processing", default=None)
        if processor is None:
            return
        worker = threading.Thread(
            target=processor.process_snapshot,
            args=(snapshot_record,),
            daemon=True,
        )
        worker.start()

    def get_status(self) -> Dict[str, Any]:
        return dict(self.status)

    def extract_crop(self, frame, card_measurement):
        if card_measurement is None:
            return None

        bbox_points = getattr(card_measurement, "bbox_points", None) or []
        if not bbox_points:
            return None

        workspace = self.context.get_service("workspace")

        # bbox_points are in card-workspace coordinates.
        # Convert them to live-frame coordinates first.
        live_points = [
            workspace.to_full_frame(point, workspace_name="card")
            for point in bbox_points
        ]

        # If frame is 4K full_frame but workspace/detection ran on live_frame,
        # scale live-frame coordinates to full-frame coordinates.
        scale = self.context.runtime.get("live_to_full_scale", {"x": 1.0, "y": 1.0})
        scale_x = float(scale.get("x", 1.0))
        scale_y = float(scale.get("y", 1.0))

        full_points = [
            (point[0] * scale_x, point[1] * scale_y)
            for point in live_points
        ]

        x_values = [int(point[0]) for point in full_points]
        y_values = [int(point[1]) for point in full_points]

        base_padding = int(self.context.config.get("snapshot", {}).get("crop_padding_px", 70))
        padding = int(base_padding * max(scale_x, scale_y))

        x_min = max(0, min(x_values) - padding)
        y_min = max(0, min(y_values) - padding)
        x_max = min(frame.shape[1], max(x_values) + padding)
        y_max = min(frame.shape[0], max(y_values) + padding)

        if x_max <= x_min or y_max <= y_min:
            return None

        return frame[y_min:y_max, x_min:x_max]

    def _write_snapshot(
        self,
        *,
        frame,
        card_measurement,
        session_id: Optional[str],
        candidate_id: Optional[str],
        question_id: Optional[str],
        prefix: str,
    ) -> SnapshotRecord:
        import cv2

        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        snapshot_id = f"{prefix}_{timestamp}_{int(time.time() * 1000)}"
        image_path = self.output_dir / f"{snapshot_id}.jpg"
        crop_path = self.output_dir / f"{snapshot_id}_crop.jpg"
        snapshot_frame = self._downscale_snapshot_frame(frame)
        cv2.imwrite(str(image_path), snapshot_frame)

        crop = self.extract_crop(frame, card_measurement)
        saved_crop_path: Optional[str] = None
        if crop is not None:
            cv2.imwrite(str(crop_path), crop)
            saved_crop_path = str(crop_path)

        return SnapshotRecord(
            snapshot_id=snapshot_id,
            candidate_id=candidate_id,
            session_id=session_id,
            question_id=question_id,
            image_path=str(image_path),
            crop_path=saved_crop_path,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _downscale_snapshot_frame(self, frame):
        import cv2

        max_edge = int(self.context.config.get("snapshot", {}).get("max_save_edge_px", 1920))
        if max_edge <= 0:
            return frame

        height, width = frame.shape[:2]
        longest_edge = max(height, width)
        if longest_edge <= max_edge:
            return frame

        scale = max_edge / float(longest_edge)
        target_width = max(1, int(round(width * scale)))
        target_height = max(1, int(round(height * scale)))
        return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

    def _get_live_size(self):
        camera_config = self.context.config.get("camera", {})
        live_config = camera_config.get("live_processing", {})

        if live_config.get("enabled", False):
            return (
                int(live_config.get("width", camera_config.get("width", 1920))),
                int(live_config.get("height", camera_config.get("height", 1080))),
            )

        return (
            int(camera_config.get("width", 1920)),
            int(camera_config.get("height", 1080)),
        )

    def draw_workspace_debug(self, frame, workspace_config, source_size=None):
        import cv2

        debug = frame.copy()

        if source_size is None:
            source_width = frame.shape[1]
            source_height = frame.shape[0]
        else:
            source_width, source_height = source_size

        scale_x = frame.shape[1] / float(source_width)
        scale_y = frame.shape[0] / float(source_height)

        def scale_rect(rect):
            x = int(rect["x"] * scale_x)
            y = int(rect["y"] * scale_y)
            w = int(rect["width"] * scale_x)
            h = int(rect["height"] * scale_y)
            return x, y, w, h

        card = workspace_config["card"]["rect_px"]
        hand = workspace_config["hand"]["rect_px"]

        card_x, card_y, card_w, card_h = scale_rect(card)
        hand_x, hand_y, hand_w, hand_h = scale_rect(hand)

        cv2.rectangle(
            debug,
            (card_x, card_y),
            (card_x + card_w, card_y + card_h),
            (0, 255, 0),
            3,
        )
        cv2.putText(
            debug,
            "card workspace",
            (card_x + 10, card_y + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )

        cv2.rectangle(
            debug,
            (hand_x, hand_y),
            (hand_x + hand_w, hand_y + hand_h),
            (255, 0, 0),
            3,
        )
        cv2.putText(
            debug,
            "hand workspace",
            (hand_x + 10, hand_y + 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 0, 0),
            2,
        )

        return debug
