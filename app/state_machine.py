from app.states.boot import BootState
from app.states.calibration import CalibrationState
from app.states.candidate_detected import CandidateDetectedState
from app.states.error_safe import ErrorSafeState
from app.states.idle import IdleNoCardState
from app.states.init_cam import InitCamState
from app.states.recovery import RecoveryState
from app.states.snapshot import SnapshotState
from app.states.tracking import TrackingState


class StateMachine:
    STATE_CLASSES = {
        "BOOT": BootState,
        "INIT_CAM": InitCamState,
        "CALIBRATION": CalibrationState,
        "IDLE_NO_CARD": IdleNoCardState,
        "CANDIDATE_DETECTED": CandidateDetectedState,
        "TRACKING": TrackingState,
        "SNAPSHOT": SnapshotState,
        "RECOVERY": RecoveryState,
        "ERROR_SAFE": ErrorSafeState,
    }

    def __init__(self, context):
        self.context = context
        self.current_state = None
        self.current_state_instance = None

    def start(self, state_name):
        self.current_state = state_name
        if self.context.logger:
            self.context.logger.info(f"Starting state machine in {state_name}")

        while self.current_state is not None:
            if self.current_state_instance is None:
                state_class = self.STATE_CLASSES.get(self.current_state)
                if state_class is None:
                    if self.context.logger:
                        self.context.logger.error(f"Unknown state: {self.current_state}")
                    break

                previous_state = self.context.runtime.get("current_state")
                self.current_state_instance = state_class(self.context)
                if self.context.logger:
                    self.context.logger.info(
                        f"STATE_TRANSITION old_state={previous_state} new_state={self.current_state_instance.name} reason=enter"
                    )
                self.current_state_instance.enter()

            next_state = self.current_state_instance.run()
            if next_state is None:
                continue

            self.current_state_instance.exit()
            if self.context.logger:
                self.context.logger.info(
                    f"STATE_TRANSITION old_state={self.current_state_instance.name} new_state={next_state} reason=complete"
                )
            self.current_state = next_state
            self.current_state_instance = None

        if self.current_state_instance is not None:
            try:
                self.current_state_instance.exit()
            except Exception:
                pass
            self.current_state_instance = None
