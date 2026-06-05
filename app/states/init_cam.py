import time
from app.services.camera_service import CameraService


class InitCamState:
    name = "INIT_CAM"

    def __init__(self, context):
        self.context = context
        self.camera_service = None

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "INIT_CAM_ENTER"
        if self.context.logger:
            self.context.logger.info("Entering INIT_CAM state")

    def run(self):
        self.context.runtime["substate"] = "INIT_CAM_CHECK_CV2"
        if self.context.logger:
            self.context.logger.info("Checking OpenCV availability")

        self.camera_service = CameraService(self.context)
        self.context.services["camera"] = self.camera_service

        try:
            self.camera_service.probe_cv2()
            if self.context.logger:
                self.context.logger.info(
                    f"OpenCV available: version={self.camera_service.cv2_version}"
                )
        except Exception as exc:
            if self.context.logger:
                self.context.logger.error(f"OpenCV probe failed: {exc}")
            return "ERROR_SAFE"

        retries = int(self.context.config.get("camera", {}).get("retry_attempts", 3))
        for attempt in range(1, retries + 1):
            self.context.runtime["substate"] = "INIT_CAM_OPEN_CAMERA"
            if self.context.logger:
                self.context.logger.info(
                    f"Camera initialization attempt {attempt}/{retries}"
                )

            try:
                self.camera_service.open()
                self.context.runtime["substate"] = "INIT_CAM_READ_FRAME"
                frame = self.camera_service.read_frame()
                self.context.runtime["substate"] = "INIT_CAM_READY"
                self.context.logger.info(
                    f"Camera frame received shape={frame.shape} cv2={self.camera_service.cv2_version}"
                )
                return "CALIBRATION"
            except Exception as exc:
                if self.context.logger:
                    self.context.logger.error(
                        f"Camera initialization attempt {attempt}/{retries} failed: {exc}"
                    )
                self.camera_service.close()
                if attempt < retries:
                    time.sleep(1.0)

        self.context.runtime["substate"] = "INIT_CAM_FAILED"
        return "RECOVERY"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting INIT_CAM state")
