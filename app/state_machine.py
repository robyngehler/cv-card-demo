from app.states.boot import BootState
from app.states.error_safe import ErrorSafeState
from app.states.idle import IdleNoCardState
from app.states.init_cam import InitCamState
from app.states.recovery import RecoveryState


class StateMachine:
    STATE_CLASSES = {
        "BOOT": BootState,
        "INIT_CAM": InitCamState,
        "IDLE_NO_CARD": IdleNoCardState,
        "RECOVERY": RecoveryState,
        "ERROR_SAFE": ErrorSafeState,
    }

    def __init__(self, context):
        self.context = context
        self.current_state = None

    def start(self, state_name):
        self.current_state = state_name
        if self.context.logger:
            self.context.logger.info(f"Starting state machine in {state_name}")

        while self.current_state is not None:
            state_class = self.STATE_CLASSES.get(self.current_state)
            if state_class is None:
                if self.context.logger:
                    self.context.logger.error(f"Unknown state: {self.current_state}")
                break

            state = state_class(self.context)
            self.context.logger.info(
                f"STATE_TRANSITION old_state={self.current_state} new_state={state.name} reason=enter"
            )
            state.enter()
            next_state = state.run()
            state.exit()

            if next_state and self.context.logger:
                self.context.logger.info(
                    f"STATE_TRANSITION old_state={state.name} new_state={next_state} reason=complete"
                )
            self.current_state = next_state
