import time

from app.utils.frame_scaling import make_live_frame


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
        candidate_loop_hz = float(
            context.config.get("identity", {}).get("precheck", {}).get("candidate_loop_hz", 2.0)
        )
        self.poll_interval = max(0.01, 1.0 / max(candidate_loop_hz, 0.1))
        self.identity_precheck_max_duration_s = float(
            context.config.get("identity", {}).get("precheck", {}).get("max_duration_s", 1.0)
        )
        self.best_frame = None
        self.best_candidate = None
        
        if context.logger:
            context.logger.info(
                f"CANDIDATE_DETECTED configured: "
                f"require_stable_frames={self.required_stable_frames}, "
                f"max_lost_frames={self.max_lost_frames}"
            )

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "CONFIRM_VISUAL_CANDIDATE"
        self.stable_frame_count = 0
        self.lost_frame_count = 0
        self.best_frame = self.context.runtime.get("last_candidate_frame")
        self.best_candidate = self.context.runtime.get("last_card_measurement")
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
        if self.context.runtime.get("ui_mode") == "CONFIGURE_CAMERA":
            self.context.runtime["substate"] = "CAMERA_CONFIG_PAUSED"
            return "IDLE_NO_CARD"

        forced_state = self.context.runtime.pop("force_state", None)
        if forced_state:
            return forced_state

        camera = self.context.get_service("camera")
        detector = self.context.get_service("detector")
        questionnaire = self.context.get_service("questionnaire", default=None)
        candidate_precheck = self.context.get_service("candidate_precheck", default=None)
        identity = self.context.get_service("identity", default=None)
        ui_service = self.context.get_service("ui", default=None)
        
        # Read frame with timeout
        full_frame = camera.read_frame(timeout_s=0.5)
        if full_frame is None:
            if self.context.logger:
                self.context.logger.warning("CANDIDATE_DETECTED: No frame available (camera lost?)")
            return "IDLE_NO_CARD"
        frame, scale_x, scale_y = make_live_frame(full_frame, self.context.config)
        self.context.runtime["last_frame"] = full_frame
        self.context.runtime["last_live_frame"] = frame
        self.context.runtime["last_live_frame_ts"] = time.time()
        self.context.runtime["live_to_full_scale"] = {
            "x": scale_x,
            "y": scale_y,
        }
        
        # Run detector
        try:
            result = detector.detect(frame, state_name=self.name)
        except Exception as e:
            if self.context.logger:
                self.context.logger.error(f"CANDIDATE_DETECTED: Detection failed: {e}")
            return "IDLE_NO_CARD"
        
        # Update runtime state
        self.context.runtime["last_detection"] = result
        
        # Temporal debouncing logic
        if result.visible and result.candidate and result.candidate.is_business_card:
            # Good detection - card found
            self.lost_frame_count = 0
            self.stable_frame_count += 1
            self.last_detection = result.candidate
            self.context.runtime["last_candidate"] = result.candidate
            self.context.runtime["last_card_measurement"] = result.candidate
            self.context.runtime["last_candidate_frame"] = full_frame
            if self.best_candidate is None or result.candidate.confidence >= self.best_candidate.confidence:
                self.best_candidate = result.candidate
                self.best_frame = full_frame
            
            if self.context.logger:
                self.context.logger.debug(
                    f"CANDIDATE_DETECTED: Good frame {self.stable_frame_count}/{self.required_stable_frames}, "
                    f"confidence={result.candidate.confidence:.3f}"
                )

            if ui_service is not None:
                ui_service.publish_score(
                    {
                        "visible": True,
                        "score": result.candidate.x_normalized,
                        "rating": round(float(result.candidate.x_normalized or 0.0) * 10.0, 1),
                        "x_normalized": result.candidate.x_normalized,
                        "confidence": result.candidate.confidence,
                        "candidates_count": result.candidates_count,
                        "state": self.name,
                        "fusion_state": "CANDIDATE_SEEN",
                        "source": "card_detector_candidate",
                        "message": "Recognizing card...",
                    }
                )
            
            # Check if card is stable enough to transition
            if self.stable_frame_count >= self.required_stable_frames:
                self.context.runtime["substate"] = "PRECHECK_IDENTITY"
                identity_status = "TEMPORARY_PRECHECK_UNRESOLVED"
                candidate_id = None
                precheck_result = None
                if candidate_precheck is not None and self.best_frame is not None and self.best_candidate is not None:
                    precheck_result = candidate_precheck.resolve_from_frame(
                        frame=self.best_frame,
                        card_measurement=self.best_candidate,
                        budget_s=self.identity_precheck_max_duration_s,
                    )
                    self.context.runtime["last_identity_precheck"] = precheck_result
                    candidate_id = precheck_result.candidate_id
                    if precheck_result.resolved:
                        identity_status = precheck_result.identity_status
                    else:
                        identity_status = "TEMPORARY_PRECHECK_UNRESOLVED"

                if candidate_id is None and identity is not None:
                    candidate_id = identity.create_temporary_candidate_id()

                if questionnaire is not None:
                    session = questionnaire.ensure_session(
                        candidate_id=candidate_id,
                        identity_status=identity_status,
                        resume_policy="resume_incomplete_or_new",
                        now=time.monotonic(),
                    )
                    session["card_identity_state"] = identity_status
                    session["identity_status"] = identity_status

                self.context.runtime["substate"] = "START_OR_RESUME_SESSION"
                if ui_service is not None:
                    ui_service.publish_score(
                        {
                            "visible": True,
                            "score": result.candidate.x_normalized,
                            "rating": round(float(result.candidate.x_normalized or 0.0) * 10.0, 1),
                            "x_normalized": result.candidate.x_normalized,
                            "confidence": result.candidate.confidence,
                            "candidates_count": result.candidates_count,
                            "state": self.name,
                            "fusion_state": "IDENTITY_PRECHECK",
                            "source": "card_crop_ocr",
                            "candidate_id": candidate_id,
                            "identity_status": identity_status,
                            "message": "Welcome back" if precheck_result and precheck_result.resolved else "New visitor",
                        }
                    )
                if self.context.logger:
                    self.context.logger.info(
                        f"CANDIDATE_DETECTED: Business card confirmed stable after {self.stable_frame_count} frames, "
                        f"transitioning to TRACKING"
                    )
                return "TRACKING"
            
            # Still confirming
            time.sleep(self.poll_interval)
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

            time.sleep(self.poll_interval)
            return None

    def exit(self):
        if self.context.logger:
            self.context.logger.info(f"Exiting CANDIDATE_DETECTED state (stable_frames={self.stable_frame_count})")
