from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any, Dict, Optional


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
            workspace = self.context.get_service("workspace", default=None)
            if workspace is None:
                return None
            return workspace.transform(frame, workspace_name="card")

        workspace = self.context.get_service("workspace")
        full_points = [workspace.to_full_frame(point, workspace_name="card") for point in bbox_points]
        x_values = [int(point[0]) for point in full_points]
        y_values = [int(point[1]) for point in full_points]
        x_min = max(0, min(x_values))
        y_min = max(0, min(y_values))
        x_max = min(frame.shape[1], max(x_values))
        y_max = min(frame.shape[0], max(y_values))
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
        cv2.imwrite(str(image_path), frame)

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
