import asyncio
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Body
from fastapi.responses import Response
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
            session = self.context.runtime.get("session", {})
            tracking = self.context.runtime.get("tracking", {})
            last_fusion = self.context.runtime.get("last_fusion_measurement")
            last_card = self.context.runtime.get("last_card_measurement")
            last_hand = self.context.runtime.get("last_hand_measurement")
            return {
                "state": self.context.runtime.get("current_state"),
                "substate": self.context.runtime.get("substate"),
                "timestamp": time.time(),
                "session": {
                    "session_id": session.get("session_id"),
                    "candidate_id": session.get("candidate_id"),
                    "identity_status": session.get("identity_status"),
                    "current_question_id": session.get("current_question_id"),
                    "phase": session.get("phase"),
                    "completed": session.get("completed"),
                    "question_index": session.get("question_index"),
                },
                "tracking": {
                    "source": tracking.get("source"),
                    "fusion_state": tracking.get("fusion_state"),
                    "last_score": getattr(last_fusion, "score", None),
                    "last_rating": getattr(last_fusion, "rating", None),
                    "visible": getattr(last_fusion, "visible", False),
                    "confidence": getattr(last_fusion, "confidence", None),
                },
                "card": {
                    "visible": bool(last_card is not None and getattr(last_card, "visible", False)),
                    "x": getattr(last_card, "x", None),
                    "y": getattr(last_card, "y", None),
                    "x_normalized": getattr(last_card, "x_normalized", None),
                    "confidence": getattr(last_card, "confidence", None),
                    "source": getattr(last_card, "source", None),
                    "bbox_points": getattr(last_card, "bbox_points", None),
                },
                "hand": {
                    "visible": bool(last_hand is not None and getattr(last_hand, "visible", False)),
                    "valid": bool(last_hand is not None and getattr(last_hand, "valid", False)),
                    "proxy_x": getattr(last_hand, "proxy_x", None),
                    "proxy_y": getattr(last_hand, "proxy_y", None),
                    "proxy_x_normalized": getattr(last_hand, "proxy_x_normalized", None),
                    "proxy_y_normalized": getattr(last_hand, "proxy_y_normalized", None),
                    "landmark_count": len(getattr(last_hand, "landmarks", {}) or {}),
                    "confidence": getattr(last_hand, "confidence", None),
                    "reason": getattr(last_hand, "reason", None),
                },
            }

        @self.app.get("/api/debug-frame")
        async def debug_frame():
            frame_bytes = self.context.runtime.get("last_debug_frame_jpeg")
            if not frame_bytes:
                return Response(status_code=204)
            return Response(content=frame_bytes, media_type="image/jpeg")

        @self.app.get("/api/version")
        async def version():
            return {
                "app": self.context.config.get("app", {}).get("name", "cv-card-demo"),
                "version": self.context.config.get("app", {}).get("version", "0.1.0"),
            }

        @self.app.get("/api/camera/settings")
        async def camera_settings():
            service = self.context.get_service("camera_control", default=None)
            if service is None:
                return {
                    "status": "NOT_INITIALIZED",
                    "settings": {},
                    "last_error": "camera_control_service_missing",
                }
            return service.get_settings()

        @self.app.get("/api/camera/capabilities")
        async def camera_capabilities():
            service = self.context.get_service("camera_control", default=None)
            if service is None:
                return {
                    "status": "NOT_INITIALIZED",
                    "settings": {},
                    "last_error": "camera_control_service_missing",
                }
            return service.get_capabilities()

        @self.app.post("/api/camera/settings")
        async def camera_apply_settings(payload: dict = Body(default_factory=dict)):
            service = self.context.get_service("camera_control", default=None)
            if service is None:
                return {
                    "status": "NOT_INITIALIZED",
                    "applied": {},
                    "rejected": {k: "camera_control_service_missing" for k in payload.keys()},
                    "last_error": "camera_control_service_missing",
                }
            return service.apply_settings(payload or {})

        @self.app.post("/api/camera/restart")
        async def camera_restart():
            service = self.context.get_service("camera_control", default=None)
            if service is None:
                return {
                    "status": "NOT_INITIALIZED",
                    "last_error": "camera_control_service_missing",
                }
            return service.restart_camera()

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
