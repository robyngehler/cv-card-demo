import cv2


def make_live_frame(full_frame, config):
    """Return live processing frame plus scale factors to map back to full frame."""
    camera_config = config.get("camera", {})
    live_config = camera_config.get("live_processing", {})

    if not live_config.get("enabled", False):
        return full_frame, 1.0, 1.0

    live_width = int(live_config.get("width", full_frame.shape[1]))
    live_height = int(live_config.get("height", full_frame.shape[0]))

    if full_frame.shape[1] == live_width and full_frame.shape[0] == live_height:
        return full_frame, 1.0, 1.0

    live_frame = cv2.resize(
        full_frame,
        (live_width, live_height),
        interpolation=cv2.INTER_AREA,
    )

    scale_x = full_frame.shape[1] / float(live_width)
    scale_y = full_frame.shape[0] / float(live_height)

    return live_frame, scale_x, scale_y
