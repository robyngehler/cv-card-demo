class ErrorSafeState:
    name = "ERROR_SAFE"

    def __init__(self, context):
        self.context = context

    def enter(self):
        self.context.runtime["current_state"] = self.name
        self.context.runtime["substate"] = "ERROR_SAFE_ENTER"
        if self.context.logger:
            self.context.logger.error("Entering ERROR_SAFE state")

    def run(self):
        if self.context.logger:
            self.context.logger.error("Critical error prevented safe startup")
        return None

    def exit(self):
        if self.context.logger:
            self.context.logger.info("Exiting ERROR_SAFE state")
