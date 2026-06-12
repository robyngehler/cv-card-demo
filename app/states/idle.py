import time

from app.utils.frame_scaling import make_live_frame


class IdleNoCardState:
    name = "IDLE_NO_CARD"

    def __init__(self, context):
        self.context = context
        self.poll_interval = float(
            self.context.config.get("camera", {}).get("idle_poll_interval", 0.5)
        )
        self.live_jpeg_quality = int(
            (context.config.get("server", {}) or {}).get("live_stream_jpeg_quality", 70)
        )
        # How long IDLE_NO_CARD must persist (no card detected) before the last
        # visitor's session is cleared and the UI returns to the true ground
        # state ("place a card"). The grace period rides out brief
        # TRACKING -> IDLE -> TRACKING blips and keeps the farewell/thanks panel
        # visible for a moment right after a snapshot, instead of wiping it
        # instantly.
        self.session_reset_idle_s = float(
            (context.config.get("questionnaire", {}) or {}).get("session_reset_idle_s", 6.0)
        )

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "IDLE_ENTER"
        # Reaching IDLE means the camera/CV pipeline is healthy again — clear the
        # ERROR_SAFE backoff so a future failure retries quickly from the start.
        self.context.runtime["error_safe_attempts"] = 0
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
                ts = time.time()
                self.context.runtime["last_frame"] = full_frame
                self.context.runtime["last_live_frame"] = frame
                self.context.runtime["last_live_frame_ts"] = ts
                self.context.runtime["live_to_full_scale"] = {
                    "x": scale_x,
                    "y": scale_y,
                }
                # Encode a clean stream frame so the live view stays fresh in
                # IDLE / CONFIGURE_CAMERA, not just during TRACKING.
                try:
                    import cv2 as _cv2
                    _ok, _enc = _cv2.imencode(
                        ".jpg", frame,
                        [int(_cv2.IMWRITE_JPEG_QUALITY), self.live_jpeg_quality],
                    )
                    if _ok:
                        self.context.runtime["last_live_frame_jpeg"] = _enc.tobytes()
                        self.context.runtime["last_live_frame_jpeg_ts"] = ts
                except Exception:
                    pass

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
                        # A card is back on the table: cancel any pending
                        # idle reset so the visitor's session is preserved.
                        self.context.runtime.pop("idle_no_card_since", None)
                        return "CANDIDATE_DETECTED"

                # No card visible this frame. If a previous visitor's session is
                # still around and the table has now been clear long enough, wipe
                # it so the UI drops back to the ground state.
                self._maybe_reset_session(time.time())

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

    def _maybe_reset_session(self, now: float) -> None:
        """Clear the previous visitor's session after a clear interruption.

        Only acts once the table has been continuously empty for
        ``session_reset_idle_s``. Keeping the name/questionnaire visible while a
        card is recognized is intentional; this only fires when the session was
        clearly abandoned (card gone a while), not during brief blips or right
        after a snapshot.
        """
        session = self.context.runtime.get("session") or {}
        # Nothing to reset if there is no leftover session.
        if not session.get("session_id"):
            self.context.runtime.pop("idle_no_card_since", None)
            return

        started = self.context.runtime.get("idle_no_card_since")
        if started is None:
            self.context.runtime["idle_no_card_since"] = now
            return

        if (now - float(started)) < self.session_reset_idle_s:
            return

        # Grace period elapsed with the table empty: drop all last-visitor state.
        self.context.runtime["session"] = {}
        questionnaire_runtime = self.context.runtime.setdefault("questionnaire", {})
        questionnaire_runtime["active"] = False
        questionnaire_runtime["pending_snapshot"] = False
        questionnaire_runtime["last_completed_question_id"] = None
        self.context.runtime.setdefault("tracking", {})["countdown_visible"] = False
        self.context.runtime["last_fusion_measurement"] = None
        self.context.runtime["last_card_measurement"] = None
        self.context.runtime["last_candidate"] = None
        self.context.runtime.pop("idle_no_card_since", None)
        if self.context.logger:
            self.context.logger.info(
                "IDLE_NO_CARD: session cleared after "
                f"{self.session_reset_idle_s:.1f}s with no card "
                f"(candidate_id={session.get('candidate_id')})"
            )

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting IDLE_NO_CARD state")
