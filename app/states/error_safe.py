import time


class ErrorSafeState:
    """Safe holding state after a critical failure.

    ERROR_SAFE keeps the process (and the UI) alive but does not touch the
    camera. Instead of staying here forever, it waits a bounded, backing-off
    interval and then retries the camera via INIT_CAM, so the booth self-heals
    once a disconnected camera is plugged back in — no manual restart needed.
    """

    name = "ERROR_SAFE"

    def __init__(self, context):
        self.context = context
        error_safe_cfg = context.config.get("error_safe", {}) or {}
        self.base_retry_interval_s = float(error_safe_cfg.get("retry_interval_s", 8.0))
        self.max_retry_interval_s = float(error_safe_cfg.get("max_retry_interval_s", 60.0))
        # auto_recover can be disabled to keep the old terminal behaviour.
        self.auto_recover = bool(error_safe_cfg.get("auto_recover", True))

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "ERROR_SAFE_ENTER"
        if self.context.logger:
            self.context.logger.error(
                "Entering ERROR_SAFE state "
                f"(auto_recover={self.auto_recover}, last_error={self.context.runtime.get('last_error')})"
            )

    def run(self):
        if not self.auto_recover:
            time.sleep(1.0)
            return None

        # Exponential backoff capped at max_retry_interval_s, persisted across
        # re-entries so repeated failures slow the retry cadence instead of
        # hammering a missing camera.
        attempts = int(self.context.runtime.get("error_safe_attempts", 0)) + 1
        self.context.runtime["error_safe_attempts"] = attempts
        interval = min(
            self.max_retry_interval_s,
            self.base_retry_interval_s * (2 ** (attempts - 1)),
        )
        self.context.runtime["substate"] = f"ERROR_SAFE_WAIT_RETRY_{attempts}"
        if self.context.logger:
            self.context.logger.warning(
                f"ERROR_SAFE: waiting {interval:.0f}s before retry attempt "
                f"{attempts} (re-initialising via INIT_CAM)"
            )

        # Sleep in small chunks so an operator-forced transition (e.g. from the
        # UI) stays responsive instead of being blocked for the full interval.
        waited = 0.0
        while waited < interval:
            forced_state = self.context.runtime.get("force_state")
            if forced_state:
                return None
            time.sleep(0.5)
            waited += 0.5

        self.context.runtime["substate"] = "ERROR_SAFE_RETRY"
        return "INIT_CAM"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting ERROR_SAFE state")
