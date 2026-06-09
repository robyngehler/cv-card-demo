import time

from app.utils.frame_scaling import make_live_frame


class IdleNoCardState:
    name = "IDLE_NO_CARD"

    def __init__(self, context):
        self.context = context
        self.poll_interval = float(
            self.context.config.get("camera", {}).get("idle_poll_interval", 0.5)
        )

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "IDLE_ENTER"
        if self.context.logger:
            self.context.logger.info("Entering IDLE_NO_CARD state")

    def run(self):
        self.context.runtime["substate"] = "IDLE_WAITING_FOR_CARD"
        if self.context.logger:
            self.context.logger.info("System is idle and waiting for a card")

        while True:
            forced_state = self.context.runtime.pop("force_state", None)
            if forced_state:
                return forced_state

            camera_service = self.context.get_service("camera", default=None)
            if camera_service is None or not getattr(camera_service, "opened", False):
                if self.context.logger:
                    self.context.logger.warning(
                        "Camera lost during IDLE_NO_CARD, transitioning to RECOVERY"
                    )
                return "RECOVERY"

            detector = self.context.get_service("detector", default=None)
            ui_service = self.context.get_service("ui", default=None)
            configure_mode = self.context.runtime.get("ui_mode") == "CONFIGURE_CAMERA"

            try:
                full_frame = camera_service.read_frame(timeout_s=0.5)
                frame, scale_x, scale_y = make_live_frame(full_frame, self.context.config)
                self.context.runtime["last_frame"] = full_frame
                self.context.runtime["last_live_frame"] = frame
                self.context.runtime["last_live_frame_ts"] = time.time()
                self.context.runtime["live_to_full_scale"] = {
                    "x": scale_x,
                    "y": scale_y,
                }

                if configure_mode:
                    self.context.runtime["substate"] = "CAMERA_CONFIG_PREVIEW"
                    time.sleep(self.poll_interval)
                    continue

                if detector is not None:
                    result = detector.detect(frame, state_name=self.name)
                    self.context.runtime["last_detection"] = result
                    if result.visible and result.candidate is not None and result.candidate.is_business_card:
                        self.context.runtime["last_candidate"] = result.candidate
                        self.context.runtime["last_card_measurement"] = result.candidate
                        self.context.runtime["last_candidate_frame"] = full_frame
                        if self.context.logger:
                            self.context.logger.info(
                                "Business-card candidate detected "
                                f"confidence={result.candidate.confidence:.2f} "
                                f"x_normalized={result.candidate.x_normalized:.2f}"
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
                                    "question_id": self.context.runtime.get("session", {}).get("current_question_id"),
                                    "candidate_id": self.context.runtime.get("session", {}).get("candidate_id"),
                                    "identity_status": self.context.runtime.get("session", {}).get("identity_status"),
                                    "message": "Recognizing card...",
                                }
                            )
                        return "CANDIDATE_DETECTED"

                if ui_service is not None:
                    ui_service.publish_score(
                        {
                            "visible": False,
                            "score": None,
                            "rating": None,
                            "x_normalized": None,
                            "confidence": 0.0,
                            "candidates_count": 0,
                            "state": self.name,
                            "fusion_state": "NO_TARGET",
                            "source": "idle",
                            "question_id": self.context.runtime.get("session", {}).get("current_question_id"),
                            "candidate_id": self.context.runtime.get("session", {}).get("candidate_id"),
                            "identity_status": self.context.runtime.get("session", {}).get("identity_status"),
                            "question_phase": self.context.runtime.get("session", {}).get("phase"),
                        }
                    )
            except Exception as exc:
                if self.context.logger:
                    self.context.logger.error(f"Idle detection loop failed: {exc}")
                return "RECOVERY"

            time.sleep(self.poll_interval)

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting IDLE_NO_CARD state")
