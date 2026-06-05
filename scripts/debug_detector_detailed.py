#!/usr/bin/env python3
"""
Card Detector Debugging Script - Shows why cards are/aren't detected.
Streams to HTTP with detailed debug information.
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


class FrameBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None
        self.debug_info = {}
    
    def set(self, frame, debug_info=None):
        with self.lock:
            self.frame = frame.copy() if frame is not None else None
            self.debug_info = debug_info or {}
    
    def get(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None, dict(self.debug_info)


class MotionJPEGHandler(BaseHTTPRequestHandler):
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
            <head><title>Detector Debug Stream</title>
            <style>body{font-family:Arial;margin:20px;}img{max-width:100%;border:2px solid #333;}</style>
            </head><body>
            <h1>Card Detector Debug Stream</h1>
            <img src="/stream.mjpg" width="640" />
            </body></html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


def draw_detector_debug(workspace_frame, contours, best_candidate, config):
    """
    Draw detailed debug information showing contours, filters, and why cards were rejected.
    """
    frame = workspace_frame.copy()
    if len(frame.shape) == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    
    frame_area = float(frame.shape[0] * frame.shape[1])
    contour_filter = config.get("contour_filter", {})
    min_area_px = int(contour_filter.get("min_area_px", 1000))
    max_area_ratio = float(contour_filter.get("max_area_ratio", 0.8))
    min_aspect_ratio = float(contour_filter.get("min_aspect_ratio", 1.2))
    max_aspect_ratio = float(contour_filter.get("max_aspect_ratio", 2.2))
    min_confidence = float(config.get("confidence", {}).get("min_confidence", 0.5))
    
    y_offset = 25
    line_height = 18
    
    cv2.putText(frame, "DETECTOR DEBUG", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    
    y_offset += line_height + 5
    cv2.putText(
        frame,
        f"Frame: {frame.shape[1]}x{frame.shape[0]} ({frame_area:.0f}px)",
        (10, y_offset),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (200, 200, 200),
        1,
    )
    
    y_offset += line_height
    cv2.putText(
        frame,
        f"Contours found: {len(contours)} | Thresholds: area>[{min_area_px}px, <{int(frame_area*max_area_ratio)}px]",
        (10, y_offset),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (200, 200, 200),
        1,
    )
    
    y_offset += line_height
    cv2.putText(
        frame,
        f"Aspect ratio: [{min_aspect_ratio:.1f}, {max_aspect_ratio:.1f}] | Min confidence: {min_confidence:.2f}",
        (10, y_offset),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (200, 200, 200),
        1,
    )
    
    y_offset += line_height + 5
    
    if best_candidate:
        candidate = best_candidate
        center = (int(candidate.x), int(candidate.y))
        cv2.circle(frame, center, 5, (0, 255, 0), -1)
        angle = -candidate.theta_deg
        size = (int(candidate.width), int(candidate.height))
        box = cv2.boxPoints(((candidate.x, candidate.y), size, angle))
        box = box.astype(int)
        cv2.polylines(frame, [box], True, (0, 255, 0), 2)
        
        cv2.putText(
            frame,
            f"✓ DETECTED: conf={candidate.confidence:.2f} x_norm={candidate.x_normalized:.2f}",
            (10, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )
    else:
        cv2.putText(
            frame,
            f"✗ No candidate found",
            (10, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            2,
        )
    
    # Draw all contours for reference (red = rejected)
    for i, contour in enumerate(contours[:20]):  # Limit to 20 for clarity
        area = cv2.contourArea(contour)
        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = box.astype(int)
        cv2.polylines(frame, [box], True, (0, 0, 255), 1)  # Red = rejected
    
    return frame


def main():
    config = load_config("config/config.yaml")
    ctx = create_app_context(config=config, logger=None)

    workspace_service = WorkspaceService(ctx)
    workspace_config = config.get("workspace", {})
    workspace_service.configure(workspace_config)

    detector = ClassicalCardDetector(ctx)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        sys.exit(1)

    frame_buffer = FrameBuffer()
    MotionJPEGHandler.frame_buffer = frame_buffer
    
    http_server = HTTPServer(("0.0.0.0", 8080), MotionJPEGHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    print("Card Detector Debug Visualizer")
    print("===============================")
    print(f"Workspace: {workspace_service.status.mode}")
    print(f"Streaming: http://localhost:8080")
    print("Press Ctrl+C to stop\n")

    frame_count = 0
    try:
        while True:
            ret, raw_frame = cap.read()
            if not ret:
                print("ERROR: Cannot read from camera")
                break

            try:
                workspace_service.validate(raw_frame.shape)
                workspace_frame = workspace_service.transform(raw_frame)
            except Exception as exc:
                print(f"Workspace error: {exc}")
                break

            result = detector.detect(workspace_frame)

            # Get detailed contour info for visualization
            preprocessing = config.get("detector", {}).get("preprocessing", {})
            grayscale = bool(preprocessing.get("grayscale", True))
            blur_kernel = int(preprocessing.get("blur_kernel", 5))
            threshold_mode = preprocessing.get("threshold_mode", "adaptive")

            frame = workspace_frame
            if grayscale and len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if blur_kernel > 1:
                if blur_kernel % 2 == 0:
                    blur_kernel += 1
                frame = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)

            if threshold_mode == "otsu":
                _, mask = cv2.threshold(frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                mask = cv2.adaptiveThreshold(
                    frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5,
                )

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

            contours_result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = contours_result[0] if len(contours_result) == 2 else contours_result[1]

            debug_frame = draw_detector_debug(workspace_frame, contours, result.candidate, config.get("detector", {}))
            frame_buffer.set(debug_frame)

            frame_count += 1
            if frame_count % 30 == 0:
                print(
                    f"[Frame {frame_count}] Contours: {len(contours)} | "
                    f"Visible: {result.visible} | Candidates: {result.candidates_count}"
                )

    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        cap.release()
        http_server.shutdown()


if __name__ == "__main__":
    main()
