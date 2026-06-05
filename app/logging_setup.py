import logging
import os


def init_logging(config):
    log_config = config.get("logging", {})
    level = log_config.get("level", "INFO").upper()
    handlers = [logging.StreamHandler()]

    if log_config.get("log_to_file", False):
        log_file = log_config.get("file")
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.isdir(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("cv-card-demo")
