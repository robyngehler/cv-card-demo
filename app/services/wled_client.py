class WledClient:
    def __init__(self, context):
        self.context = context
        self.enabled = bool(self.context.config.get("wled", {}).get("enabled", False))
        self.host = self.context.config.get("wled", {}).get("host", "")

    def is_available(self):
        return self.enabled and bool(self.host)
