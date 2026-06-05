#!/usr/bin/env python3
"""
Interactive Card Detector Debug Visualizer

This script provides a live preview of the card detection pipeline.

Mode 1 (with display): Press 'q' to quit, 'r' to refresh, 's' to save frame, 'p' to toggle pause.
Mode 2 (headless): Streams Motion JPEG over HTTP at http://localhost:8080/stream.mjpg
"""

import sys
import os
import time
import threading
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.app_context import create_app_context
from app.config_loader import load_config
from app.cv.classical_card_detector import ClassicalCardDetector
from app.services.workspace_service import WorkspaceService

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler


def create_test_card_image(width: int = 1080, height: int = 720) -> np.ndarray:
    """
    Create a synthetic test image with a realistic business card.
    Simulates a business card on a table.
    """
    frame = np.full((height, width, 3), 80, dtype=np.uint8)
    
    card_x, card_y = 150, 120
    card_width, card_height = 320, 180
    
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_width, card_y + card_height), (240, 240, 240), -1)
    
    cv2.rectangle(frame, (card_x, card_y), (card_x + card_width, card_y + card_height), (50, 50, 50), 2)
    
    cv2.putText(
        frame,
        "BUSINESS CARD",
        (card_x + 40, card_y + 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (50, 50, 50),
        2,
    )
    cv2.putText(
        frame,
        "Name | Company",
        (card_x + 40, card_y + 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (100, 100, 100),
        1,
    )
    
    return frame


class FrameBuffer:
    """Thread-safe frame buffer for HTTP streaming."""
    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None
        self.frame_count = 0
    
    def set(self, frame):
        with self.lock:
            self.frame = frame.copy() if frame is not None else None
            self.frame_count += 1
    
    def get(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None, self.frame_count


class MotionJPEGHandler(BaseHTTPRequestHandler):
    """HTTP handler for Motion JPEG streaming."""
    frame_buffer = None
    
    def do_GET(self):
        if self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            
            while True:
                frame, _ = self.frame_buffer.get()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ret:
                    continue
                
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(buffer)}\r\n\r\n".encode())
                self.wfile.write(buffer.tobytes())
                self.wfile.write(b"\r\n")
        
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = """
            <html>
            <head>
                <title>Card Detector Live Stream</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    img { max-width: 100%; border: 2px solid #333; }
                    h1 { color: #333; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <h1>Card Detector Live Stream</h1>
                <p>Streaming from <code>localhost:8080</code></p>
                <img src="/stream.mjpg" width="640" />
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def main():
    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)

    workspace_service = WorkspaceService(ctx)
    workspace_config = config.get("workspace", {})
    workspace_service.configure(workspace_config)

    detector = ClassicalCardDetector(ctx)

    use_camera = False
    if len(sys.argv) > 1 and sys.argv[1] == "camera":
        use_camera = True

    if use_camera:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("ERROR: Could not open camera. Falling back to test image.")
            use_camera = False

    print("Card Detector Debug Visualizer")
    print("==============================")
    print("")
    print(f"Using: {'Camera' if use_camera else 'Test Image'}")
    print(f"Workspace mode: {workspace_service.status.mode}")
    print("")

    # Try cv2.imshow first
    use_imshow = False
    try:
        test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imshow("Test", test_frame)
        cv2.waitKey(1)
        cv2.destroyWindow("Test")
        use_imshow = True
        print("✓ Display available, using cv2.imshow")
        print("  Controls: q=quit, SPACE=pause, s=save, r=reload config")
    except cv2.error:
        print("✗ Display not available (GTK+ not compiled)")
        print("✓ Falling back to Motion JPEG HTTP streaming")
        print("  Open browser: http://localhost:8080")
        use_imshow = False

    print("")

    # Start HTTP server if no display
    http_server = None
    frame_buffer = None
    if not use_imshow:
        frame_buffer = FrameBuffer()
        MotionJPEGHandler.frame_buffer = frame_buffer
        
        http_server = HTTPServer(("0.0.0.0", 8080), MotionJPEGHandler)
        http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        http_thread.start()
        print("  HTTP server started on port 8080")
        print("")

    paused = False
    frame_count = 0

    try:
        while True:
            if not paused:
                if use_camera:
                    ret, raw_frame = cap.read()
                    if not ret:
                        print("ERROR: Could not read from camera")
                        break
                else:
                    raw_frame = create_test_card_image(width=640, height=480)

                try:
                    workspace_service.validate(raw_frame.shape)
                    workspace_frame = workspace_service.transform(raw_frame)
                except Exception as exc:
                    print(f"Workspace error: {exc}")
                    break

                result = detector.detect(workspace_frame)
                debug_frame = detector.draw_debug(workspace_frame, result)

                frame_count += 1
                if frame_count % 30 == 0:
                    print(
                        f"[Frame {frame_count}] "
                        f"visible={result.visible} "
                        f"candidates={result.candidates_count} "
                        f"status={result.status}"
                    )
                    if result.visible and result.candidate:
                        print(
                            f"  → confidence={result.candidate.confidence:.3f} "
                            f"x_norm={result.candidate.x_normalized:.3f} "
                            f"angle={result.candidate.theta_deg:.1f}°"
                        )
                
                # Send frame to HTTP server
                if frame_buffer is not None:
                    frame_buffer.set(debug_frame)
                
                # Try to display with cv2.imshow
                if use_imshow:
                    cv2.imshow("Card Detector Debug", debug_frame)
                    key = cv2.waitKey(30) & 0xFF

                    if key == ord("q"):
                        print("Quitting...")
                        break
                    elif key == ord(" "):
                        paused = not paused
                        state = "PAUSED" if paused else "RUNNING"
                        print(f"Pause toggled: {state}")
                    elif key == ord("s"):
                        filename = f"frame_{time.time():.0f}.png"
                        cv2.imwrite(filename, debug_frame)
                        print(f"Saved frame to {filename}")
                    elif key == ord("r"):
                        config = load_config("config/config.yaml")
                        ctx = create_app_context(config=config, logger=None)
                        workspace_service = WorkspaceService(ctx)
                        workspace_service.configure(config.get("workspace", {}))
                        detector = ClassicalCardDetector(ctx)
                        print("Config reloaded")
                else:
                    # Headless mode: poll for keyboard input
                    time.sleep(0.03)
            else:
                debug_frame_paused = np.zeros_like(debug_frame) if 'debug_frame' in locals() else np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    debug_frame_paused,
                    "PAUSED",
                    (280, 240),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 255),
                    2,
                )
                if frame_buffer is not None:
                    frame_buffer.set(debug_frame_paused)
                
                if use_imshow:
                    cv2.imshow("Card Detector Debug", debug_frame_paused)
                    key = cv2.waitKey(100) & 0xFF
                    if key == ord(" "):
                        paused = False
                        print("Pause toggled: RUNNING")
                else:
                    time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        if use_imshow:
            cv2.destroyAllWindows()
        if use_camera:
            cap.release()
        if http_server:
            http_server.shutdown()
        print("Done.")


if __name__ == "__main__":
    main()
