import asyncio
import json
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import Body
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from uvicorn import Config, Server
from app.utils.frame_scaling import make_live_frame


class UIService:
    def __init__(self, context):
        self.context = context
        self.app = FastAPI()
        self.active_status_connections = []
        self.active_score_connections = []
        self.active_sse_connections = 0
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
            snapshot = self._build_ui_snapshot()
            session = snapshot.get("session", {})
            tracking = snapshot.get("tracking", {})
            return {
                "state": snapshot.get("app", {}).get("state"),
                "substate": snapshot.get("app", {}).get("substate"),
                "timestamp": snapshot.get("timestamp"),
                "session": {
                    "session_id": session.get("session_id"),
                    "candidate_id": session.get("candidate_id"),
                    "identity_status": session.get("identity_status"),
                    "current_question_id": session.get("current_question_id"),
                    "phase": snapshot.get("questionnaire", {}).get("phase"),
                    "completed": session.get("completed"),
                    "question_index": session.get("question_index"),
                },
                "tracking": {
                    "source": tracking.get("source"),
                    "fusion_state": tracking.get("fusion_state"),
                    "last_score": snapshot.get("questionnaire", {}).get("score"),
                    "last_rating": snapshot.get("questionnaire", {}).get("rating"),
                    "visible": tracking.get("card_visible") or tracking.get("hand_visible"),
                    "confidence": tracking.get("confidence"),
                },
                "card": snapshot.get("card", {}),
                "hand": snapshot.get("hand", {}),
            }

        @self.app.get("/api/ui/snapshot")
        async def ui_snapshot():
            return self._build_ui_snapshot()

        @self.app.get("/api/ui/events")
        async def ui_events():
            return StreamingResponse(
                self._stream_ui_events(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.app.post("/api/mode/configure-camera")
        async def mode_configure_camera():
            runtime = self.context.runtime
            runtime["ui_mode"] = "CONFIGURE_CAMERA"
            runtime["substate"] = "CAMERA_CONFIG_ACTIVE"
            if runtime.get("current_state") in ("TRACKING", "CANDIDATE_DETECTED", "SNAPSHOT"):
                runtime["force_state"] = "IDLE_NO_CARD"
            return {
                "status": "OK",
                "mode": "CONFIGURE_CAMERA",
                "state": runtime.get("current_state"),
                "timestamp": time.time(),
            }

        @self.app.post("/api/mode/run")
        async def mode_run():
            runtime = self.context.runtime
            runtime["ui_mode"] = "RUN"
            runtime["substate"] = "RUN_ACTIVE"
            return {
                "status": "OK",
                "mode": "RUN",
                "state": runtime.get("current_state"),
                "timestamp": time.time(),
            }

        @self.app.get("/api/debug-frame")
        async def debug_frame():
            frame_bytes = self.context.runtime.get("last_debug_frame_jpeg")
            if not frame_bytes:
                return Response(status_code=204)
            return Response(content=frame_bytes, media_type="image/jpeg")

        @self.app.get("/api/live-frame")
        async def live_frame(mode: str = "run"):
            frame_bytes, frame_ts = self._get_live_frame_jpeg(mode=mode)
            if not frame_bytes:
                return Response(status_code=204)
            return Response(
                content=frame_bytes,
                media_type="image/jpeg",
                headers={"X-Frame-Timestamp": str(frame_ts)},
            )

        @self.app.get("/api/live.mjpeg")
        async def live_mjpeg(mode: str = "run"):
            return StreamingResponse(
                self._stream_live_mjpeg(mode=mode),
                media_type="multipart/x-mixed-replace; boundary=frame",
                headers={
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )

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

    def _build_ui_snapshot(self):
        runtime = self.context.runtime
        session = runtime.get("session", {})
        tracking = runtime.get("tracking", {})
        question = self._questionnaire_payload()
        last_fusion = runtime.get("last_fusion_measurement")
        last_card = runtime.get("last_card_measurement")
        last_hand = runtime.get("last_hand_measurement")
        camera = self.context.get_service("camera", default=None)
        camera_control = self.context.get_service("camera_control", default=None)
        health = self.context.get_service("health", default=None)

        snapshot = {
            "type": "ui_snapshot",
            "timestamp": time.time(),
            "app": {
                "state": runtime.get("current_state"),
                "substate": runtime.get("substate"),
                "mode": runtime.get("ui_mode", "RUN"),
            },
            "session": {
                "session_id": session.get("session_id"),
                "candidate_id": session.get("candidate_id"),
                "identity_status": session.get("identity_status"),
                "question_index": session.get("question_index", 0),
                "question_count": self._question_count(),
                "current_question_id": session.get("current_question_id"),
                "completed": bool(session.get("completed")),
            },
            "questionnaire": question,
            "tracking": {
                "source": tracking.get("source", getattr(last_fusion, "source", "idle")),
                "fusion_state": tracking.get("fusion_state", getattr(last_fusion, "fusion_state", "NO_TARGET")),
                "confidence": getattr(last_fusion, "confidence", None),
                "score": getattr(last_fusion, "score", None),
                "rating": getattr(last_fusion, "rating", None),
                "card_visible": bool(last_card is not None and getattr(last_card, "visible", False)),
                "hand_visible": bool(last_hand is not None and getattr(last_hand, "visible", False)),
                "candidates_count": getattr(runtime.get("last_detection"), "candidates_count", 0),
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
            "camera": {
                "mode": "configure" if runtime.get("ui_mode") == "CONFIGURE_CAMERA" else "tracking",
                "opened": bool(getattr(camera, "opened", False)),
                "frame_shape": getattr(camera, "frame_shape", None),
                "settings_status": (
                    camera_control.get_status().get("status") if camera_control is not None else "NOT_INITIALIZED"
                ),
                "last_error": camera_control.last_error if camera_control is not None else "camera_control_service_missing",
                "last_frame_ts": runtime.get("last_live_frame_ts") or getattr(camera, "last_frame_timestamp", None),
            },
            "services": {
                "detector": self._service_status("detector"),
                "hand_tracker": self._service_status("hand_tracker"),
                "snapshot_processing": self._service_status("snapshot_processing"),
                "ocr": self._service_status("ocr"),
                "vector": self._service_status("vector"),
                "health": "OK" if health is not None else "NOT_INITIALIZED",
            },
        }
        runtime["last_ui_snapshot"] = snapshot
        runtime["last_ui_snapshot_ts"] = snapshot["timestamp"]
        return snapshot

    def _questionnaire_payload(self):
        session = self.context.runtime.get("session", {})
        question_service = self.context.get_service("questionnaire", default=None)
        question = None
        if question_service is not None:
            current_question = getattr(question_service, "current_question", None)
            if callable(current_question):
                try:
                    question = current_question()
                except Exception:
                    question = None

        last_fusion = self.context.runtime.get("last_fusion_measurement")
        score = getattr(last_fusion, "score", None)
        rating = getattr(last_fusion, "rating", None)
        phase = session.get("phase", "WAIT_FOR_MOVEMENT")
        countdown_started_at = session.get("countdown_started_at")
        countdown_remaining_s = None
        if phase == "COUNTDOWN" and countdown_started_at and question is not None:
            elapsed = max(0.0, time.monotonic() - float(countdown_started_at))
            countdown_remaining_s = max(0.0, float(getattr(question, "countdown_s", 3.0)) - elapsed)

        return {
            "phase": phase,
            "question_label": getattr(question, "label", None) or "Place a business card to begin",
            "min_label": getattr(question, "min_label", None) or "0",
            "max_label": getattr(question, "max_label", None) or "10",
            "score": score,
            "rating": rating,
            "visible": bool(getattr(last_fusion, "visible", False)),
            "countdown_remaining_s": countdown_remaining_s,
            "snapshot_pending": bool(self.context.runtime.get("questionnaire", {}).get("pending_snapshot", False)),
            "message": self._phase_message(phase),
        }

    def _phase_message(self, phase):
        if phase == "WAIT_FOR_MOVEMENT":
            return "Move the business card to choose a score"
        if phase == "ACTIVE_SCORING":
            return "Live scoring active"
        if phase == "WAIT_FOR_STABILITY":
            return "Hold position to lock answer"
        if phase == "COUNTDOWN":
            return "Hold still"
        if phase == "SNAPSHOT_PENDING":
            return "Capturing"
        if phase == "DONE":
            return "Questionnaire complete"
        return "System ready"

    def _question_count(self):
        questionnaire = self.context.get_service("questionnaire", default=None)
        if questionnaire is None:
            return 0
        questions = getattr(questionnaire, "questions", None)
        if questions is None:
            return 0
        return len(questions)

    def _service_status(self, service_name):
        service = self.context.get_service(service_name, default=None)
        if service is None:
            return "NOT_INITIALIZED"
        get_status = getattr(service, "get_status", None)
        if callable(get_status):
            try:
                status_payload = get_status()
                if isinstance(status_payload, dict):
                    return status_payload.get("status", "OK")
            except Exception:
                return "ERROR"
        return "OK"

    async def _stream_ui_events(self):
        self.active_sse_connections += 1
        interval_s = float(self.context.config.get("server", {}).get("ui_events_interval_s", 0.33))
        interval_s = max(0.1, interval_s)
        try:
            while True:
                try:
                    snapshot = self._build_ui_snapshot()
                    payload = json.dumps(snapshot)
                    yield f"event: ui_snapshot\\ndata: {payload}\\n\\n"
                except Exception as exc:
                    if self.context.logger:
                        self.context.logger.warning(f"UI events snapshot build failed: {exc}")
                    payload = json.dumps({"type": "ui_heartbeat", "timestamp": time.time()})
                    yield f"event: ui_heartbeat\\ndata: {payload}\\n\\n"
                await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            return
        finally:
            self.active_sse_connections = max(0, self.active_sse_connections - 1)

    def _get_live_frame_jpeg(self, mode="run"):
        runtime = self.context.runtime
        frame_ts = runtime.get("last_live_frame_ts") or time.time()
        mode_upper = str(mode or "run").upper()
        if mode_upper == "RUN":
            debug_bytes = runtime.get("last_debug_frame_jpeg")
            if debug_bytes:
                return debug_bytes, frame_ts

        frame = runtime.get("last_live_frame")
        if frame is None:
            frame = self._capture_live_frame_once()
        if frame is None:
            return None, frame_ts

        try:
            import cv2
        except Exception:
            return None, frame_ts

        overlay = frame.copy()
        if len(overlay.shape) == 2:
            overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR)

        workspace = self.context.get_service("workspace", default=None)
        if workspace is not None:
            for name, color in (("card", (82, 222, 151)), ("hand", (245, 171, 53))):
                definition = workspace.workspaces.get(name)
                if definition is None or definition.rect_px is None:
                    continue
                x, y, w, h = definition.rect_px
                cv2.rectangle(overlay, (int(x), int(y)), (int(x + w), int(y + h)), color, 2)
                cv2.putText(
                    overlay,
                    f"{name} workspace",
                    (int(x), max(18, int(y) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

        fusion = self.context.runtime.get("last_fusion_measurement")
        cv2.putText(
            overlay,
            f"mode={self.context.runtime.get('ui_mode', 'RUN')} state={self.context.runtime.get('current_state')} source={getattr(fusion, 'source', 'idle')}",
            (18, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            overlay,
            f"ts={frame_ts:.3f}",
            (18, 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
        )
        success, encoded = cv2.imencode(
            ".jpg",
            overlay,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(self.context.config.get("server", {}).get("live_stream_jpeg_quality", 70))],
        )
        if not success:
            return None, frame_ts
        return encoded.tobytes(), frame_ts

    def _capture_live_frame_once(self):
        camera = self.context.get_service("camera", default=None)
        runtime = self.context.runtime
        frame = runtime.get("last_frame")
        cached_live = runtime.get("last_live_frame")
        last_live_ts = runtime.get("last_live_frame_ts")
        min_interval = float(self.context.config.get("server", {}).get("live_capture_min_interval_s", 0.12))
        min_interval = max(0.02, min_interval)

        if cached_live is not None and last_live_ts is not None:
            try:
                if (time.time() - float(last_live_ts)) <= min_interval:
                    return cached_live
            except Exception:
                pass

        frame = None
        read_from_camera = False
        try:
            if camera is not None and getattr(camera, "opened", False):
                frame = camera.read_frame(timeout_s=0.08)
                read_from_camera = frame is not None
        except Exception:
            frame = None

        if frame is None:
            frame = runtime.get("last_frame")
            if frame is None:
                frame = runtime.get("last_live_frame")
        if frame is None:
            return None

        try:
            live_frame, scale_x, scale_y = make_live_frame(frame, self.context.config)
            if read_from_camera:
                runtime["last_frame"] = frame
            runtime["last_live_frame"] = live_frame
            runtime["last_live_frame_ts"] = time.time()
            runtime["live_to_full_scale"] = {"x": scale_x, "y": scale_y}
            return live_frame
        except Exception:
            return None

    async def _stream_live_mjpeg(self, mode="run"):
        fps = float(self.context.config.get("server", {}).get("live_stream_fps", 8.0))
        sleep_s = max(0.02, 1.0 / max(1.0, fps))
        while True:
            frame_bytes, frame_ts = self._get_live_frame_jpeg(mode=mode)
            if frame_bytes is not None:
                yield (
                    b"--frame\\r\\n"
                    b"Content-Type: image/jpeg\\r\\n"
                    + f"X-Frame-Timestamp: {frame_ts}\\r\\n\\r\\n".encode("ascii")
                    + frame_bytes
                    + b"\\r\\n"
                )
            await asyncio.sleep(sleep_s)
