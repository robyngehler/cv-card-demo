import argparse
import time

from app.app_context import create_app_context
from app.config_loader import load_config
from app.logging_setup import init_logging
from app.services.candidate_precheck_service import CandidatePrecheckService
from app.services.card_detector_service import CardDetectorService
from app.services.health_service import HealthService
from app.services.fusion_tracker_service import CardHandFusionTracker
from app.services.hand_tracker_service import MediaPipeHandTracker
from app.services.identity_service import CandidateIdentityResolver
from app.services.ocr_service import BusinessCardMetadataPipeline
from app.services.persistence_service import SQLitePersistenceService
from app.services.questionnaire_service import ConfigDrivenQuestionnaireRuntime
from app.services.snapshot_processing_service import SnapshotProcessingService
from app.services.snapshot_service import SnapshotService
from app.services.ui_service import UIService
from app.services.vector_service import VectorService
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

    ctx.register_service("health", HealthService(ctx))
    ctx.register_service("ui", UIService(ctx))
    ctx.register_service("workspace", WorkspaceService(ctx))
    ctx.register_service("detector", CardDetectorService(ctx))
    ctx.register_service("hand_tracker", MediaPipeHandTracker(ctx))
    ctx.register_service("fusion_tracker", CardHandFusionTracker(ctx))
    ctx.register_service("identity", CandidateIdentityResolver(ctx))
    ctx.register_service("questionnaire", ConfigDrivenQuestionnaireRuntime(ctx))
    ctx.register_service("persistence", SQLitePersistenceService(ctx))
    ctx.register_service("vector", VectorService(ctx))
    ctx.register_service("ocr", BusinessCardMetadataPipeline(ctx))
    ctx.register_service("snapshot", SnapshotService(ctx))
    ctx.register_service("snapshot_processing", SnapshotProcessingService(ctx))
    ctx.register_service("candidate_precheck", CandidatePrecheckService(ctx))

    if config.get("wled", {}).get("enabled", False):
        ctx.register_service("wled", WledClient(ctx))

    state_machine = StateMachine(ctx)
    ctx.state_machine = state_machine
    state_machine.start(args.initial_state)


if __name__ == "__main__":
    main()
