from app.services.health_service import HealthService
from app.services.ui_service import UIService


class BootState:
    name = "BOOT"

    def __init__(self, context):
        self.context = context

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "BOOT_ENTER"
        if self.context.logger:
            self.context.logger.info("Entering BOOT state")

    def run(self):
        self.context.runtime["substate"] = "BOOT_LOAD_CONFIG"
        if not self._validate_config():
            return "ERROR_SAFE"

        self.context.runtime["substate"] = "BOOT_INIT_LOGGING"
        if self.context.services.get("ui") is None:
            self.context.services["ui"] = UIService(self.context)

        if self.context.services.get("health") is None:
            self.context.services["health"] = HealthService(self.context)

        # The optional WLED output adapter is registered in main.py
        # (WledOutputService); BOOT does not need to create it. WLED must never
        # be a BOOT dependency.

        self.context.runtime["substate"] = "BOOT_START_UI_SERVICE"
        try:
            self.context.services["ui"].start()
        except Exception as exc:
            if self.context.logger:
                self.context.logger.error(f"UI service failed to start: {exc}")
            return "ERROR_SAFE"

        self.context.runtime["substate"] = "BOOT_READY"
        if self.context.logger:
            self.context.logger.info("BOOT complete, transitioning to INIT_CAM")
        return "INIT_CAM"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting BOOT state")

    def _validate_config(self):
        config = self.context.config
        required_sections = ["app", "server", "boot", "camera", "logging"]
        for section in required_sections:
            if section not in config:
                if self.context.logger:
                    self.context.logger.error(f"Missing required config section: {section}")
                return False

        server = config["server"]
        if not isinstance(server.get("port"), int):
            if self.context.logger:
                self.context.logger.error("Server port must be an integer")
            return False

        if not server.get("ui_static_dir"):
            if self.context.logger:
                self.context.logger.error("UI static directory is not configured")
            return False

        return True
