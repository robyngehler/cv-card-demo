import asyncio
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from uvicorn import Config, Server


class UIService:
    def __init__(self, context):
        self.context = context
        self.app = FastAPI()
        self.active_status_connections = []
        self.active_score_connections = []
        self.server = None
        self.thread = None
        self.event_loop = None
        self._setup_routes()

    def _setup_routes(self):
        ui_dir = self.context.config.get("server", {}).get("ui_static_dir", "./app/web")

        @self.app.get("/api/health")
        async def health():
            return self.context.services["health"].get_status()

        @self.app.get("/api/state")
        async def state():
            return {
                "state": self.context.runtime.get("current_state"),
                "substate": self.context.runtime.get("substate"),
            }

        @self.app.get("/api/version")
        async def version():
            return {
                "app": self.context.config.get("app", {}).get("name", "cv-card-demo"),
                "version": self.context.config.get("app", {}).get("version", "0.1.0"),
            }

        @self.app.websocket("/ws/status")
        async def websocket_status(websocket: WebSocket):
            await websocket.accept()
            self.active_status_connections.append(websocket)
            try:
                while True:
                    await asyncio.sleep(10)
            except WebSocketDisconnect:
                self.active_status_connections.remove(websocket)

        @self.app.websocket("/ws/score")
        async def websocket_score(websocket: WebSocket):
            await websocket.accept()
            self.active_score_connections.append(websocket)
            try:
                while True:
                    await asyncio.sleep(10)
            except WebSocketDisconnect:
                self.active_score_connections.remove(websocket)

        # Register static web app last so API and WS routes are not shadowed.
        self.app.mount("/", StaticFiles(directory=ui_dir, html=True), name="web")

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        host = self.context.config.get("server", {}).get("host", "0.0.0.0")
        port = int(self.context.config.get("server", {}).get("port", 8000))
        config = Config(
            self.app,
            host=host,
            port=port,
            log_level="info",
            loop="asyncio",
            lifespan="on",
        )
        self.server = Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        if self.context.logger:
            self.context.logger.info(f"UI service started on http://{host}:{port}")

    def publish_score(self, score):
        """
        Publish a score update to all connected score WebSocket clients.
        
        This method provides a synchronous interface to the async broadcast_score.
        It's safe to call from the state machine's synchronous context.
        
        Args:
            score (dict): Score data with keys like visible, score, x_normalized, confidence, state, source
        """
        if self.server and not self.server.should_exit and getattr(self.server, "server", None):
            # Try to schedule broadcast on the server's event loop
            try:
                # Create a new coroutine to broadcast
                coro = self.broadcast_score(score)
                
                # Try to run it in the server's event loop
                # This is a best-effort approach; if the loop is busy, we may lose updates
                asyncio.run_coroutine_threadsafe(coro, self.server.server.loop)
            except Exception as e:
                # Non-critical: WebSocket publish is best-effort
                if self.context.logger:
                    self.context.logger.debug(f"UI score publish failed (non-critical): {e}")

    async def broadcast_status(self, message):
        payload = {"type": "system_status", "message": message}
        for websocket in list(self.active_status_connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.active_status_connections.remove(websocket)

    async def broadcast_score(self, score):
        payload = {"type": "score_update", "score": score}
        for websocket in list(self.active_score_connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                self.active_score_connections.remove(websocket)
