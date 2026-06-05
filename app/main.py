import argparse
import time

from app.app_context import create_app_context
from app.config_loader import load_config
from app.cv.classical_card_detector import ClassicalCardDetector
from app.logging_setup import init_logging
from app.services.health_service import HealthService
from app.services.ui_service import UIService
from app.services.workspace_service import WorkspaceService
from app.services.wled_client import WledClient
from app.state_machine import StateMachine


def parse_args():
    parser = argparse.ArgumentParser(description="CV Card Demo backend")
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    parser.add_argument("--initial-state", default="BOOT", help="Initial state to start")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config(args.config)
    logger = init_logging(config)
    ctx = create_app_context(config=config, logger=logger)
    ctx.runtime["start_time"] = time.time()
    ctx.runtime["boot_id"] = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    ctx.services["health"] = HealthService(ctx)
    ctx.services["ui"] = UIService(ctx)
    ctx.services["workspace"] = WorkspaceService(ctx)
    ctx.services["detector"] = ClassicalCardDetector(ctx)

    if config.get("wled", {}).get("enabled", False):
        ctx.services["wled"] = WledClient(ctx)

    state_machine = StateMachine(ctx)
    ctx.state_machine = state_machine
    state_machine.start(args.initial_state)


if __name__ == "__main__":
    main()
