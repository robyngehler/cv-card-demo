#!/usr/bin/env python3
"""
Quick script to check actual camera resolution and debug workspace configuration.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera")
    sys.exit(1)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

print("Camera Info")
print("===========")
print(f"Resolution: {width} x {height}")
print(f"FPS: {fps}")

# Read one frame to verify
ret, frame = cap.read()
if ret:
    print(f"Actual frame shape: {frame.shape}")

print()
print("Suggested Workspace Config:")
print("===========================")
print(f"width: {int(width * 0.8)}")
print(f"height: {int(height * 0.7)}")
print(f"x: {int(width * 0.1)}")
print(f"y: {int(height * 0.15)}")

cap.release()
