import time

from app.cv.card_tracker import CardTracker

class TrackingState:
    """
    Active card tracking state.
    
    Continuously tracks the card position and publishes normalized score
    to UI via WebSocket. Handles brief occlusions with temporal smoothing.
    Transitions back to IDLE if card is lost for too long.
    """
    name = "TRACKING"

    def __init__(self, context):
        self.context = context
        
        # Load config
        tracking_config = context.config.get("tracking", {})
        camera_config = context.config.get("camera", {})
        fps = float(camera_config.get("fps", 30) or 30)
        self.poll_interval = float(tracking_config.get("poll_interval_s", max(0.01, 1.0 / fps)))
        self.publish_last_position_during_occlusion = bool(
            tracking_config.get("publish_last_position_during_occlusion", True)
        )
        self.tracker = CardTracker(
            max_lost_duration_s=float(tracking_config.get("tracking_max_lost_duration_s", 0.5)),
            match_max_distance_px=float(tracking_config.get("tracking_match_max_distance_px", 80.0)),
            prediction_enabled=bool(tracking_config.get("tracking_prediction_enabled", True)),
            velocity_smoothing_alpha=float(tracking_config.get("tracking_velocity_smoothing_alpha", 0.6)),
        )

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "TRACKING_ENTER"
        self.tracker.reset()
        last_candidate = self.context.runtime.get("last_candidate")
        if hasattr(last_candidate, "x"):
            self.tracker.initialize(last_candidate)
        
        if self.context.logger:
            self.context.logger.info(
                "Entering TRACKING state "
                f"(max_lost_duration_s={self.tracker.max_lost_duration_s:.2f}, "
                f"poll_interval_s={self.poll_interval:.3f})"
            )

    def run(self):
        """
        Main tracking loop.
        
        1. Read frame and detect card
        2. If visible: publish score, reset lost counter
        3. If not visible: increment lost counter
        4. If lost > threshold: transition back to IDLE_NO_CARD
        """
        self.context.runtime["substate"] = "TRACKING_ACTIVE"
        
        from app.services.camera_service import CameraService
        from app.services.workspace_service import WorkspaceService
        from app.services.ui_service import UIService
        from app.cv.classical_card_detector import ClassicalCardDetector
        
        try:
            camera = self.context.get_service(CameraService)
            workspace_service = self.context.get_service(WorkspaceService)
            detector = self.context.get_service(ClassicalCardDetector)
            ui_service = self.context.get_service(UIService)
        except Exception as e:
            if self.context.logger:
                self.context.logger.error(f"TRACKING: Failed to get services: {e}")
            return "IDLE_NO_CARD"
        
        # Read frame
        try:
            frame = camera.read_frame(timeout_s=0.5)
            if frame is None:
                if self.context.logger:
                    self.context.logger.warning("TRACKING: No frame available (camera lost?)")
                return "IDLE_NO_CARD"
        except Exception as e:
            if self.context.logger:
                self.context.logger.warning(f"TRACKING: Camera read failed: {e}")
            return "RECOVERY"
        
        # Transform to workspace
        try:
            workspace_frame = workspace_service.transform(frame)
        except Exception as e:
            if self.context.logger:
                self.context.logger.warning(f"TRACKING: Workspace transform failed: {e}")
            return "IDLE_NO_CARD"
        
        # Detect card
        try:
            result = detector.detect(workspace_frame)
        except Exception as e:
            if self.context.logger:
                self.context.logger.warning(f"TRACKING: Detection failed: {e}")
            return "IDLE_NO_CARD"
        
        now = time.monotonic()

        # Update runtime
        self.context.runtime["last_detection"] = result
        
        matched_candidate = None
        if result.visible and result.candidate:
            matched_candidate = self.tracker.match_candidate(result.candidates or [result.candidate], now=now)
            if matched_candidate is None and not self.tracker.is_initialized():
                matched_candidate = result.candidate

        if matched_candidate is not None:
            self.tracker.update(matched_candidate, now=now)
            self.context.runtime["last_candidate"] = matched_candidate
            self._publish_score(
                ui_service,
                matched_candidate,
                source="detected",
                candidates_count=result.candidates_count,
            )
            time.sleep(self.poll_interval)
            return None

        lost_duration_s = self.tracker.lost_duration(now=now)
        if self.context.logger:
            self.context.logger.debug(
                "TRACKING: detector lost card "
                f"lost_duration_s={lost_duration_s:.3f} "
                f"max_lost_duration_s={self.tracker.max_lost_duration_s:.3f}"
            )

        if self.publish_last_position_during_occlusion and self.tracker.has_recent_track(now=now):
            predicted_pose = self.tracker.predicted_pose(frame_width=workspace_frame.shape[1], now=now)
            if predicted_pose is not None:
                self.context.runtime["last_candidate"] = predicted_pose
                self._publish_score(
                    ui_service,
                    predicted_pose,
                    source="tracked_occluded",
                    candidates_count=result.candidates_count,
                )
                time.sleep(self.poll_interval)
                return None

        if self.context.logger:
            self.context.logger.info(
                "TRACKING: Card lost beyond tolerance, transitioning to IDLE_NO_CARD "
                f"lost_duration_s={lost_duration_s:.3f}"
            )
        self._publish_lost(ui_service)
        return "IDLE_NO_CARD"

    def _publish_score(self, ui_service, pose, *, source, candidates_count):
        if not ui_service:
            return

        score = {
            "visible": True,
            "score": pose.x_normalized,
            "x_normalized": pose.x_normalized,
            "confidence": pose.confidence,
            "candidates_count": candidates_count,
            "state": self.name,
            "source": source,
        }
        try:
            ui_service.publish_score(score)
        except Exception as e:
            if self.context.logger:
                self.context.logger.debug(f"TRACKING: UI publish failed (non-critical): {e}")

    def _publish_lost(self, ui_service):
        if not ui_service:
            return

        try:
            ui_service.publish_score(
                {
                    "visible": False,
                    "score": None,
                    "x_normalized": None,
                    "confidence": 0.0,
                    "candidates_count": 0,
                    "state": "IDLE_NO_CARD",
                    "source": "lost",
                }
            )
        except Exception:
            pass

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting TRACKING state")
