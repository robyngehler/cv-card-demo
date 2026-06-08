import time


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

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "TRACKING_ENTER"
        fusion_tracker = self.context.get_service("fusion_tracker", default=None)
        if fusion_tracker is not None:
            fusion_tracker.reset()

        if self.context.logger:
            self.context.logger.info(
                "Entering TRACKING state "
                f"(poll_interval_s={self.poll_interval:.3f})"
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
        
        try:
            camera = self.context.get_service("camera")
            workspace_service = self.context.get_service("workspace")
            detector = self.context.get_service("detector")
            hand_tracker = self.context.get_service("hand_tracker", default=None)
            fusion_tracker = self.context.get_service("fusion_tracker")
            questionnaire = self.context.get_service("questionnaire", default=None)
            ui_service = self.context.get_service("ui", default=None)
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
            self.context.runtime["last_frame"] = frame
        except Exception as e:
            if self.context.logger:
                self.context.logger.warning(f"TRACKING: Camera read failed: {e}")
            return "RECOVERY"

        # Detect card
        try:
            result = detector.detect(frame, state_name=self.name)
        except Exception as e:
            if self.context.logger:
                self.context.logger.warning(f"TRACKING: Detection failed: {e}")
            return "IDLE_NO_CARD"
        
        now = time.monotonic()

        # Update runtime
        self.context.runtime["last_detection"] = result
        
        matched_candidate = None
        if result.visible and result.candidate and result.candidate.is_business_card:
            matched_candidate = result.candidate

        card_measurement = None
        if matched_candidate is not None:
            self.context.runtime["last_candidate"] = matched_candidate
            card_measurement = matched_candidate
            self.context.runtime["last_card_measurement"] = matched_candidate

        hand_measurement = None
        if hand_tracker is not None:
            hand_measurement = hand_tracker.detect(frame, now=now)
        self.context.runtime["last_hand_measurement"] = hand_measurement

        session = self.context.runtime.get("session", {})
        if questionnaire is not None and not session.get("session_id") and card_measurement is not None:
            if self.context.logger:
                self.context.logger.warning("TRACKING: Session missing, creating fallback temporary session")
            questionnaire.ensure_session(
                candidate_id=None,
                identity_status="TEMPORARY_TRACKING_FALLBACK",
                resume_policy="resume_incomplete_or_new",
                now=now,
            )
            session = self.context.runtime.get("session", {})

        fusion_measurement = fusion_tracker.update(
            card_measurement,
            hand_measurement,
            now=now,
        )
        self.context.runtime["last_fusion_measurement"] = fusion_measurement
        self.context.runtime.setdefault("tracking", {})["source"] = fusion_measurement.source
        self.context.runtime.setdefault("tracking", {})["fusion_state"] = fusion_measurement.fusion_state
        self.context.runtime.setdefault("tracking", {})["last_visible_score"] = fusion_measurement.score

        questionnaire_context = {}
        if questionnaire is not None:
            questionnaire_context = questionnaire.update(fusion_measurement, now=now)

        self._publish_score(
            ui_service,
            fusion_measurement,
            result.candidates_count,
            questionnaire_context,
            hand_measurement,
            card_measurement,
        )
        self._update_debug_frame(
            frame,
            workspace_service,
            card_measurement,
            hand_measurement,
            fusion_measurement,
        )

        if questionnaire is not None and questionnaire.consume_snapshot_request():
            return "SNAPSHOT"

        if not fusion_measurement.visible and fusion_measurement.fusion_state == "NO_TARGET":
            if self.context.logger:
                self.context.logger.info("TRACKING: No valid target remaining, transitioning to IDLE_NO_CARD")
            return "IDLE_NO_CARD"

        time.sleep(self.poll_interval)
        return None

    def _publish_score(
        self,
        ui_service,
        fusion_measurement,
        candidates_count,
        questionnaire_context,
        hand_measurement,
        card_measurement,
    ):
        if not ui_service:
            return

        score = {
            "visible": fusion_measurement.visible,
            "score": fusion_measurement.score,
            "rating": fusion_measurement.rating,
            "x_normalized": fusion_measurement.x_normalized,
            "confidence": fusion_measurement.confidence,
            "candidates_count": candidates_count,
            "state": self.name,
            "source": fusion_measurement.source,
            "fusion_state": fusion_measurement.fusion_state,
            "question_id": questionnaire_context.get("question_id"),
            "candidate_id": questionnaire_context.get("candidate_id"),
            "identity_status": questionnaire_context.get("identity_status"),
            "question_label": questionnaire_context.get("question_label"),
            "question_phase": questionnaire_context.get("phase"),
            "question_index": questionnaire_context.get("question_index"),
            "countdown_remaining_s": questionnaire_context.get("countdown_remaining_s"),
            "question_min_label": questionnaire_context.get("question_min_label"),
            "question_max_label": questionnaire_context.get("question_max_label"),
            "message": questionnaire_context.get("message"),
            "debug": {
                "hand_visible": bool(hand_measurement is not None and hand_measurement.visible),
                "hand_valid": bool(hand_measurement is not None and hand_measurement.valid),
                "card_visible": bool(card_measurement is not None and getattr(card_measurement, "visible", False)),
                "card_source": getattr(card_measurement, "source", None),
                **fusion_measurement.debug,
            },
        }
        try:
            ui_service.publish_score(score)
        except Exception as e:
            if self.context.logger:
                self.context.logger.debug(f"TRACKING: UI publish failed (non-critical): {e}")

    def _update_debug_frame(
        self,
        frame,
        workspace_service,
        card_measurement,
        hand_measurement,
        fusion_measurement,
    ):
        try:
            import cv2
        except Exception:
            return

        overlay = frame.copy()
        if len(overlay.shape) == 2:
            overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR)

        for name, color in (("card", (82, 222, 151)), ("hand", (245, 171, 53))):
            workspace = workspace_service.workspaces.get(name)
            if workspace is None or workspace.rect_px is None:
                continue
            rect_x, rect_y, rect_width, rect_height = workspace.rect_px
            cv2.rectangle(
                overlay,
                (int(rect_x), int(rect_y)),
                (int(rect_x + rect_width), int(rect_y + rect_height)),
                color,
                2,
            )
            cv2.putText(
                overlay,
                f"{name} workspace",
                (int(rect_x), max(18, int(rect_y) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        if card_measurement is not None:
            bbox_points = getattr(card_measurement, "bbox_points", None) or []
            if bbox_points:
                full_points = [workspace_service.to_full_frame(point, workspace_name="card") for point in bbox_points]
                polyline = [
                    [int(point[0]), int(point[1])]
                    for point in full_points
                ]
                cv2.polylines(overlay, [cv2.UMat(polyline).get() if False else __import__("numpy").array(polyline, dtype="int32")], True, (82, 222, 151), 2)
            center_x, center_y = workspace_service.to_full_frame((card_measurement.x, card_measurement.y), workspace_name="card")
            cv2.circle(overlay, (int(center_x), int(center_y)), 5, (82, 222, 151), -1)

        if hand_measurement is not None and hand_measurement.landmarks:
            for point in hand_measurement.landmarks.values():
                full_x, full_y = workspace_service.to_full_frame(point, workspace_name="hand")
                cv2.circle(overlay, (int(full_x), int(full_y)), 4, (245, 171, 53), -1)
            if hand_measurement.proxy_x is not None and hand_measurement.proxy_y is not None:
                proxy_x, proxy_y = workspace_service.to_full_frame(
                    (hand_measurement.proxy_x, hand_measurement.proxy_y),
                    workspace_name="card",
                )
                cv2.circle(overlay, (int(proxy_x), int(proxy_y)), 8, (255, 255, 255), 2)

        cv2.putText(
            overlay,
            f"state={fusion_measurement.fusion_state} source={fusion_measurement.source}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            overlay,
            f"score={fusion_measurement.score if fusion_measurement.score is not None else 'None'} rating={fusion_measurement.rating if fusion_measurement.rating is not None else 'None'}",
            (20, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )

        success, encoded = cv2.imencode(".jpg", overlay)
        if success:
            self.context.runtime["last_debug_frame_jpeg"] = encoded.tobytes()

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting TRACKING state")

