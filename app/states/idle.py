import time

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
            camera_service = self.context.services.get("camera")
            if camera_service is None or not getattr(camera_service, "opened", False):
                if self.context.logger:
                    self.context.logger.warning(
                        "Camera lost during IDLE_NO_CARD, transitioning to RECOVERY"
                    )
                return "RECOVERY"

            workspace_service = self.context.services.get("workspace")
            detector = self.context.services.get("detector")

            try:
                frame = camera_service.read_frame(timeout_s=0.5)
                if workspace_service is not None:
                    workspace_frame = workspace_service.transform(frame)
                else:
                    workspace_frame = frame

                if detector is not None:
                    result = detector.detect(workspace_frame)
                    self.context.runtime["last_detection"] = {
                        "visible": result.visible,
                        "candidates_count": result.candidates_count,
                        "status": result.status,
                    }
                    if result.visible and result.candidate is not None:
                        self.context.runtime["last_candidate"] = result.candidate
                        if self.context.logger:
                            self.context.logger.info(
                                f"Card candidate detected confidence={result.candidate.confidence:.2f} x_normalized={result.candidate.x_normalized:.2f}"
                            )
                        return "CANDIDATE_DETECTED"
            except Exception as exc:
                if self.context.logger:
                    self.context.logger.error(f"Idle detection loop failed: {exc}")
                return "RECOVERY"

            time.sleep(self.poll_interval)

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting IDLE_NO_CARD state")
