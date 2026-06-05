from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Optional

from app.cv.classical_card_detector import CardPose, clamp


@dataclass
class TrackerSnapshot:
    pose: CardPose
    source: str
    lost_duration_s: float


class CardTracker:
    def __init__(
        self,
        *,
        max_lost_duration_s: float,
        match_max_distance_px: float,
        prediction_enabled: bool,
        velocity_smoothing_alpha: float,
    ):
        self.max_lost_duration_s = max(0.0, float(max_lost_duration_s))
        self.match_max_distance_px = max(0.0, float(match_max_distance_px))
        self.prediction_enabled = bool(prediction_enabled)
        self.velocity_smoothing_alpha = clamp(float(velocity_smoothing_alpha), 0.0, 1.0)
        self.reset()

    def reset(self) -> None:
        self.last_pose: Optional[CardPose] = None
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_seen_time: Optional[float] = None
        self.last_update_time: Optional[float] = None
        self.tracking_source = "lost"

    def is_initialized(self) -> bool:
        return self.last_pose is not None and self.last_seen_time is not None

    def initialize(self, pose: CardPose, now: Optional[float] = None) -> None:
        timestamp = time.monotonic() if now is None else now
        self.last_pose = pose
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_seen_time = timestamp
        self.last_update_time = timestamp
        self.tracking_source = "detected"

    def update(self, pose: CardPose, now: Optional[float] = None) -> CardPose:
        timestamp = time.monotonic() if now is None else now
        if not self.is_initialized():
            self.initialize(pose, now=timestamp)
            return pose

        assert self.last_pose is not None
        assert self.last_update_time is not None

        dt = max(timestamp - self.last_update_time, 1e-6)
        measured_vx = (pose.x - self.last_pose.x) / dt
        measured_vy = (pose.y - self.last_pose.y) / dt
        alpha = self.velocity_smoothing_alpha
        self.velocity_x = (alpha * measured_vx) + ((1.0 - alpha) * self.velocity_x)
        self.velocity_y = (alpha * measured_vy) + ((1.0 - alpha) * self.velocity_y)
        self.last_pose = pose
        self.last_seen_time = timestamp
        self.last_update_time = timestamp
        self.tracking_source = "detected"
        return pose

    def lost_duration(self, now: Optional[float] = None) -> float:
        if self.last_seen_time is None:
            return math.inf
        timestamp = time.monotonic() if now is None else now
        return max(0.0, timestamp - self.last_seen_time)

    def has_recent_track(self, now: Optional[float] = None) -> bool:
        return self.is_initialized() and self.lost_duration(now=now) <= self.max_lost_duration_s

    def predicted_pose(self, frame_width: int, now: Optional[float] = None) -> Optional[CardPose]:
        if not self.is_initialized():
            return None

        assert self.last_pose is not None
        timestamp = time.monotonic() if now is None else now
        dt = 0.0 if self.last_seen_time is None else max(0.0, timestamp - self.last_seen_time)

        if self.prediction_enabled:
            predicted_x = self.last_pose.x + (self.velocity_x * dt)
            predicted_y = self.last_pose.y + (self.velocity_y * dt)
        else:
            predicted_x = self.last_pose.x
            predicted_y = self.last_pose.y

        predicted_x = clamp(predicted_x / float(frame_width), 0.0, 1.0) * float(frame_width)
        x_normalized = clamp(predicted_x / float(frame_width), 0.0, 1.0)

        self.tracking_source = "tracked_occluded"
        return CardPose(
            visible=True,
            x=float(predicted_x),
            y=float(predicted_y),
            theta_deg=self.last_pose.theta_deg,
            width=self.last_pose.width,
            height=self.last_pose.height,
            confidence=max(0.0, self.last_pose.confidence * 0.6),
            x_normalized=x_normalized,
        )

    def predicted_center(self, now: Optional[float] = None) -> Optional[tuple[float, float]]:
        if not self.is_initialized():
            return None

        assert self.last_pose is not None
        timestamp = time.monotonic() if now is None else now
        dt = 0.0 if self.last_seen_time is None else max(0.0, timestamp - self.last_seen_time)
        if not self.prediction_enabled:
            return (self.last_pose.x, self.last_pose.y)
        return (
            self.last_pose.x + (self.velocity_x * dt),
            self.last_pose.y + (self.velocity_y * dt),
        )

    def match_candidate(self, candidates: list[CardPose], now: Optional[float] = None) -> Optional[CardPose]:
        if not candidates:
            return None
        if not self.is_initialized():
            return max(candidates, key=lambda pose: pose.confidence)

        predicted_center = self.predicted_center(now=now)
        target_x = self.last_pose.x if predicted_center is None else predicted_center[0]
        target_y = self.last_pose.y if predicted_center is None else predicted_center[1]

        nearest = min(candidates, key=lambda pose: math.hypot(pose.x - target_x, pose.y - target_y))
        distance = math.hypot(nearest.x - target_x, nearest.y - target_y)
        if distance <= self.match_max_distance_px:
            return nearest
        return None