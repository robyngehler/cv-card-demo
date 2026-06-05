class RecoveryState:
    name = "RECOVERY"

    def __init__(self, context):
        self.context = context

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "RECOVERY_ENTER"
        if self.context.logger:
            self.context.logger.warning("Entering RECOVERY state")

    def run(self):
        if self.context.logger:
            self.context.logger.warning("Recovery is not implemented; moving to ERROR_SAFE")
        return "ERROR_SAFE"

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting RECOVERY state")
