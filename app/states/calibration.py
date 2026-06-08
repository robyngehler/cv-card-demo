from app.services import camera_service
from app.services import workspace_service
from app.services.workspace_service import WorkspaceService
from app.utils.frame_scaling import make_live_frame


class CalibrationState:
    name = "CALIBRATION"

    def __init__(self, context):
        self.context = context

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "CALIBRATION_ENTER"
        if self.context.logger:
            self.context.logger.info("Entering CALIBRATION state")

    def run(self):
        self.context.runtime["substate"] = "CALIBRATION_LOAD_WORKSPACE_CONFIG"
        workspace_service = self.context.services.get("workspace")
        if workspace_service is None:
            workspace_service = WorkspaceService(self.context)
            self.context.services["workspace"] = workspace_service

        camera_service = self.context.services.get("camera")
        if camera_service is None or not getattr(camera_service, "opened", False):
            if self.context.logger:
                self.context.logger.error("Camera service is not ready for calibration")
            return "RECOVERY"

        workspace_config = self.context.config.get("workspace", {})
        workspace_service.configure(workspace_config)

        try:
            frame = camera_service.read_frame(timeout_s=1.0)
            if frame is None:
                raise RuntimeError("Camera returned no frame during calibration")

            live_frame, scale_x, scale_y = make_live_frame(frame, self.context.config)
            self.context.runtime["last_frame"] = frame
            self.context.runtime["last_live_frame"] = live_frame
            self.context.runtime["live_to_full_scale"] = {
                "x": scale_x,
                "y": scale_y,
            }

            self.context.runtime["substate"] = "CALIBRATION_VALIDATE_WORKSPACE"
            workspace_service.validate(live_frame.shape)
            self.context.runtime["substate"] = "CALIBRATION_READY"

            if self.context.logger:
                workspace_status = workspace_service.get_status()
                workspaces = workspace_status.get("workspaces", {})
                card = workspaces.get("card", {})
                hand = workspaces.get("hand", {})

                self.context.logger.info(
                    "Workspace ready "
                    f"status={workspace_status.get('status')} "
                    f"card={card.get('width')}x{card.get('height')} "
                    f"hand={hand.get('width')}x{hand.get('height')}"
                )

            return "IDLE_NO_CARD"
        except ValueError as exc:
            if self.context.logger:
                self.context.logger.error(f"Workspace calibration failed: {exc}")
            return "ERROR_SAFE"
        except Exception as exc:
            if self.context.logger:
                self.context.logger.error(f"Workspace calibration could not read a valid frame: {exc}")
            return "RECOVERY"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting CALIBRATION state")
