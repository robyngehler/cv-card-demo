class CandidateDetectedState:
    name = "CANDIDATE_DETECTED"

    def __init__(self, context):
        self.context = context
        self.stable_frame_count = 0
        self.lost_frame_count = 0
        self.last_detection = None
        
        # Load config thresholds
        tracking_config = context.config.get("tracking", {})
        self.required_stable_frames = tracking_config.get("candidate_required_frames", 3)
        self.max_lost_frames = tracking_config.get("candidate_max_lost_frames", 2)
        
        if context.logger:
            context.logger.info(
                f"CANDIDATE_DETECTED configured: "
                f"require_stable_frames={self.required_stable_frames}, "
                f"max_lost_frames={self.max_lost_frames}"
            )

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "CANDIDATE_DETECTED_ENTER"
        self.stable_frame_count = 0
        self.lost_frame_count = 0
        if self.context.logger:
            self.context.logger.info("Entering CANDIDATE_DETECTED state, waiting for stable card")

    def run(self):
        """
        Run candidate confirmation loop with temporal debouncing.
        
        Waits for N stable frames before confirming card detection.
        Accepts up to M lost frames (hand tap) without resetting.
        
        Returns:
            "TRACKING" - card confirmed stable after N frames
            "IDLE_NO_CARD" - card lost for >M frames
            None - stay in this state
        """
        from app.services.camera_service import CameraService
        from app.services.workspace_service import WorkspaceService
        from app.cv.classical_card_detector import ClassicalCardDetector
        
        camera = self.context.get_service(CameraService)
        workspace_service = self.context.get_service(WorkspaceService)
        detector = self.context.get_service(ClassicalCardDetector)
        
        # Read frame with timeout
        frame = camera.read_frame(timeout_s=0.5)
        if frame is None:
            if self.context.logger:
                self.context.logger.warning("CANDIDATE_DETECTED: No frame available (camera lost?)")
            return "IDLE_NO_CARD"
        
        # Transform frame to workspace
        try:
            workspace_frame = workspace_service.transform(frame)
        except Exception as e:
            if self.context.logger:
                self.context.logger.error(f"CANDIDATE_DETECTED: Workspace transform failed: {e}")
            return "IDLE_NO_CARD"
        
        # Run detector
        try:
            result = detector.detect(workspace_frame)
        except Exception as e:
            if self.context.logger:
                self.context.logger.error(f"CANDIDATE_DETECTED: Detection failed: {e}")
            return "IDLE_NO_CARD"
        
        # Update runtime state
        self.context.runtime["last_detection"] = result
        
        # Temporal debouncing logic
        if result.visible and result.candidate:
            # Good detection - card found
            self.lost_frame_count = 0
            self.stable_frame_count += 1
            self.last_detection = result.candidate
            self.context.runtime["last_candidate"] = result.candidate
            
            if self.context.logger:
                self.context.logger.debug(
                    f"CANDIDATE_DETECTED: Good frame {self.stable_frame_count}/{self.required_stable_frames}, "
                    f"confidence={result.candidate.confidence:.3f}"
                )
            
            # Check if card is stable enough to transition
            if self.stable_frame_count >= self.required_stable_frames:
                if self.context.logger:
                    self.context.logger.info(
                        f"CANDIDATE_DETECTED: Card confirmed stable after {self.stable_frame_count} frames, "
                        f"transitioning to TRACKING"
                    )
                return "TRACKING"
            
            # Still confirming
            return None
        
        else:
            # Lost frame - but don't fail immediately (hand tap tolerance)
            self.lost_frame_count += 1
            
            if self.context.logger:
                self.context.logger.debug(
                    f"CANDIDATE_DETECTED: Lost frame {self.lost_frame_count}/{self.max_lost_frames}, "
                    f"keeping last detection for up to {self.max_lost_frames} frames"
                )
            
            # Check if we've exceeded tolerance
            if self.lost_frame_count > self.max_lost_frames:
                if self.context.logger:
                    self.context.logger.info(
                        f"CANDIDATE_DETECTED: Card lost for {self.lost_frame_count} frames "
                        f"(exceeded max {self.max_lost_frames}), transitioning to IDLE_NO_CARD"
                    )
                return "IDLE_NO_CARD"
            
            # Still within tolerance, stay in this state
            # Publish last known detection to UI for smooth experience
            if self.last_detection:
                self.context.runtime["last_candidate"] = self.last_detection
            
            return None

    def exit(self):
        if self.context.logger:
            self.context.logger.info(f"Exiting CANDIDATE_DETECTED state (stable_frames={self.stable_frame_count})")
