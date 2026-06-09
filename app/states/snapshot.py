class SnapshotState:
    name = "SNAPSHOT"

    def __init__(self, context):
        self.context = context

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "SNAPSHOT_ENTER"
        if self.context.logger:
            self.context.logger.info("Entering SNAPSHOT state")

    def run(self):
        if self.context.runtime.get("ui_mode") == "CONFIGURE_CAMERA":
            self.context.runtime["substate"] = "CAMERA_CONFIG_PAUSED"
            return "IDLE_NO_CARD"

        forced_state = self.context.runtime.pop("force_state", None)
        if forced_state:
            return forced_state

        questionnaire = self.context.get_service("questionnaire", default=None)
        snapshot_service = self.context.get_service("snapshot", default=None)
        persistence = self.context.get_service("persistence", default=None)
        ui_service = self.context.get_service("ui", default=None)
        camera = self.context.get_service("camera", default=None)

        fusion_measurement = self.context.runtime.get("last_fusion_measurement")
        if questionnaire is None or snapshot_service is None or fusion_measurement is None:
            return "IDLE_NO_CARD"

        session = self.context.runtime.get("session", {})
        if fusion_measurement.score is None:
            return "IDLE_NO_CARD"

        frame = self.context.runtime.get("last_frame")
        if frame is None and camera is not None:
            frame = camera.read_frame(timeout_s=0.5)
            self.context.runtime["last_frame"] = frame

        card_measurement = self.context.runtime.get("last_card_measurement")
        answer_payload = questionnaire.build_answer_payload(fusion_measurement)
        snapshot_record = snapshot_service.capture(
            frame=frame,
            card_measurement=card_measurement,
            session_id=session.get("session_id"),
            candidate_id=session.get("candidate_id"),
            question_id=session.get("current_question_id"),
        )

        if persistence is not None:
            persistence.save_answer(answer_payload)
            persistence.save_snapshot(
                {
                    "snapshot_id": snapshot_record.snapshot_id,
                    "candidate_id": snapshot_record.candidate_id,
                    "session_id": snapshot_record.session_id,
                    "image_path": snapshot_record.image_path,
                    "crop_path": snapshot_record.crop_path,
                    "ocr_text": None,
                    "extraction_json": None,
                    "created_at": snapshot_record.created_at,
                }
            )

        snapshot_service.enqueue_processing(snapshot_record)
        progression = questionnaire.complete_snapshot(answer_payload)

        if progression.get("completed") and persistence is not None and session.get("session_id"):
            persistence.complete_session(session_id=session.get("session_id"), state="COMPLETED")

        if ui_service is not None:
            ui_service.publish_score(
                {
                    "visible": True,
                    "score": fusion_measurement.score,
                    "rating": fusion_measurement.rating,
                    "x_normalized": fusion_measurement.x_normalized,
                    "confidence": fusion_measurement.confidence,
                    "candidates_count": 0,
                    "state": self.name,
                    "fusion_state": fusion_measurement.fusion_state,
                    "source": "snapshot_captured",
                    "question_id": answer_payload.get("question_id"),
                    "candidate_id": answer_payload.get("candidate_id"),
                    "identity_status": session.get("identity_status"),
                    "question_phase": "SNAPSHOT",
                    "message": "Saving answer...",
                    "debug": {
                        "snapshot_id": snapshot_record.snapshot_id,
                        "image_path": snapshot_record.image_path,
                        "crop_path": snapshot_record.crop_path,
                        "completed": progression.get("completed"),
                    },
                }
            )

        if progression.get("completed"):
            return "IDLE_NO_CARD"

        if getattr(self.context.runtime.get("last_fusion_measurement"), "visible", False):
            return "TRACKING"

        return "CANDIDATE_DETECTED"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting SNAPSHOT state")