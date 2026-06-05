---
applyTo: "**/*"
---

# Hardware and Software Instructions

## Target Hardware

The target system is:

- NVIDIA Jetson Orin NX
- Ubuntu 22.04.5 LTS
- JetPack 6.1
- Jetson Linux R36.4.x
- ARMv8 / aarch64

## Camera Setup

Assume:

- one top-down RGB camera
- camera is fixed above the table
- the workspace is planar
- lighting should be stable
- the table background should be controlled
- only one main card is expected in the active workspace

## Optional LED Setup

Later optional output path:

- ESP32
- WLED
- 60 LEDs
- HTTP/JSON communication

For now, LED output is not required for the MVP.

## Primary Software Stack

Prefer:

```text
Python 3
OpenCV / cv2
NumPy
FastAPI
WebSockets
YAML
systemd
HTML/CSS/JavaScript
```

## Optional Software

Use only when needed:

```text
GStreamer
pypylon
Ultralytics YOLO-seg
ONNX
TensorRT
WLED JSON API
```

## Avoid in MVP

Do not introduce without explicit instruction:

```text
ROS2
Docker Compose
Kubernetes
Databases
Message brokers
Cloud backends
React/Vue/Svelte
Authentication
Multi-user systems
```

## Platform Notes

The Jetson is the deployment target, but development code should remain as portable as reasonably possible.

Do not hard-code Jetson-specific paths unless they are deployment scripts or documented configuration defaults.
