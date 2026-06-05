class HealthService:
    def __init__(self, context):
        self.context = context

    def get_status(self):
        cfg = self.context.config
        return {
            "app": cfg.get("app", {}).get("name", "cv-card-demo"),
            "version": cfg.get("app", {}).get("version", "0.1.0"),
            "state": self.context.runtime.get("current_state"),
            "substate": self.context.runtime.get("substate"),
            "uptime_s": self._uptime_seconds(),
            "services": {
                "ui": self._ui_status(),
                "camera": self._camera_status(),
                "workspace": self._workspace_status(),
                "detector": self._detector_status(),
                "cv2": self._cv2_status(),
                "wled": {"status": self._wled_status()},
            },
            "next_state": cfg.get("boot", {}).get("next_state", "INIT_CAM"),
        }

    def _uptime_seconds(self):
        start_time = self.context.runtime.get("start_time")
        if start_time is None:
            return 0.0
        import time

        return round(max(0.0, time.time() - start_time), 2)

    def _ui_status(self):
        return {"status": "OK" if self.context.services.get("ui") is not None else "ERROR"}

    def _camera_status(self):
        camera = self.context.services.get("camera")
        if camera is None:
            return {"status": "NOT_INITIALIZED"}

        status = {
            "status": "OK" if getattr(camera, "opened", False) else "ERROR",
        }
        if getattr(camera, "device_index", None) is not None:
            status["device_index"] = camera.device_index
        if getattr(camera, "frame_shape", None) is not None:
            status["frame_shape"] = camera.frame_shape
        if getattr(camera, "frames_read", None) is not None:
            status["frames_read"] = camera.frames_read
        return status

    def _workspace_status(self):
        workspace = self.context.services.get("workspace")
        if workspace is None:
            return {"status": "NOT_INITIALIZED"}
        return workspace.get_status()

    def _detector_status(self):
        detector = self.context.services.get("detector")
        if detector is None:
            return {"status": "NOT_INITIALIZED"}
        return detector.get_status()

    def _cv2_status(self):
        camera = self.context.services.get("camera")
        if camera is None or camera.cv2_version is None:
            return {"status": "NOT_CHECKED"}
        return {"status": "OK", "version": camera.cv2_version}

    def _wled_status(self):
        wled = self.context.services.get("wled")
        if wled is None:
            return "OPTIONAL_DISABLED"
        return "OK" if wled.is_available() else "DEGRADED"
