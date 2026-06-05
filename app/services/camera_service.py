import time


class CameraService:
    def __init__(self, context):
        self.context = context
        self.capture = None
        self.frame_shape = None
        self.opened = False
        self.cv2_version = None
        self.device_index = None
        self.frames_read = 0
        self.last_frame_timestamp = None

    def probe_cv2(self):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is not available") from exc

        self.cv2_version = cv2.__version__
        return cv2

    def open(self):
        cv2 = self.probe_cv2()
        camera_config = self.context.config.get("camera", {})
        device_index = int(camera_config.get("device_index", 0))
        self.device_index = device_index
        self.context.logger.info(f"Opening camera device {device_index}")
        capture = cv2.VideoCapture(device_index)
        if not capture.isOpened():
            raise RuntimeError(f"Camera device {device_index} could not be opened")

        self.capture = capture
        self.opened = True
        return capture

    def read_frame(self, timeout_s=2.0):
        if not self.capture or not self.opened:
            raise RuntimeError("Camera is not opened")

        start = time.monotonic()
        while time.monotonic() - start < timeout_s:
            ret, frame = self.capture.read()
            if ret and frame is not None:
                self.frame_shape = frame.shape
                self.frames_read += 1
                self.last_frame_timestamp = time.time()
                return frame
            time.sleep(0.05)

        raise RuntimeError("Timed out waiting for a valid camera frame")

    def close(self):
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass
        self.capture = None
        self.opened = False
