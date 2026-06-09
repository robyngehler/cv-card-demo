class RecoveryState:
    name = "RECOVERY"

    def __init__(self, context):
        self.context = context
        cfg = context.config.get("camera", {})
        self.max_attempts = int(cfg.get("retry_attempts", 3))
        self.retry_delay_s = float(cfg.get("recovery_retry_delay_s", 0.8))

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "RECOVERY_ENTER"
        if self.context.logger:
            self.context.logger.warning("Entering RECOVERY state")

    def run(self):
        camera = self.context.get_service("camera", default=None)
        if camera is None:
            if self.context.logger:
                self.context.logger.warning("RECOVERY: camera service missing, reinitializing via INIT_CAM")
            return "INIT_CAM"

        for attempt in range(1, self.max_attempts + 1):
            self.context.runtime["substate"] = f"RECOVERY_CAMERA_ATTEMPT_{attempt}"
            try:
                camera.close()
            except Exception:
                pass

            try:
                camera.open()
                frame = camera.read_frame(timeout_s=0.6)
                self.context.runtime["last_frame"] = frame
                if self.context.logger:
                    self.context.logger.info(
                        f"RECOVERY: camera restored on attempt {attempt}/{self.max_attempts}"
                    )
                return "IDLE_NO_CARD"
            except Exception as exc:
                self.context.runtime["last_error"] = str(exc)
                if self.context.logger:
                    self.context.logger.warning(
                        f"RECOVERY: attempt {attempt}/{self.max_attempts} failed: {exc}"
                    )
                import time

                time.sleep(self.retry_delay_s)

        if self.context.logger:
            self.context.logger.error("RECOVERY: unable to restore camera, escalating to ERROR_SAFE")
        return "ERROR_SAFE"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting RECOVERY state")
