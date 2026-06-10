import time

import cv2


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
        width = int(camera_config.get("width", 1280))
        height = int(camera_config.get("height", 720))
        fps = float(camera_config.get("fps", 30))
        fourcc = camera_config.get("fourcc", "MJPG")
        backend_name = str(camera_config.get("preferred_backend", "opencv")).lower()

        self.device_index = device_index
        self.context.logger.info(
            f"Opening camera device {device_index} requested={width}x{height}@{fps} fourcc={fourcc}"
        )

        if backend_name == "v4l2":
            capture = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
        else:
            capture = cv2.VideoCapture(device_index)

        if not capture.isOpened():
            raise RuntimeError(f"Camera device {device_index} could not be opened")

        # Important for Logitech BRIO: set MJPG before resolution/fps.
        if fourcc:
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            capture.set(cv2.CAP_PROP_FPS, fps)

        # The consumers poll slower than the camera FPS; without this the V4L2
        # queue keeps several frames and every read returns a stale frame.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Read one frame after setting properties, so the driver actually applies them.
        ret, frame = capture.read()
        if not ret or frame is None:
            capture.release()
            raise RuntimeError("Camera opened but did not return a valid frame after configuration")

        actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = capture.get(cv2.CAP_PROP_FPS)
        actual_fourcc_int = int(capture.get(cv2.CAP_PROP_FOURCC))
        actual_fourcc = "".join(
            chr((actual_fourcc_int >> (8 * i)) & 0xFF)
            for i in range(4)
        )

        self.capture = capture
        self.opened = True
        self.frame_shape = frame.shape

        self.context.logger.info(
            f"Camera configured requested={width}x{height}@{fps} fourcc={fourcc} "
            f"actual={actual_width}x{actual_height}@{actual_fps} fourcc={actual_fourcc} "
            f"first_frame_shape={frame.shape}"
        )

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
