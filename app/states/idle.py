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

            time.sleep(self.poll_interval)

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting IDLE_NO_CARD state")
