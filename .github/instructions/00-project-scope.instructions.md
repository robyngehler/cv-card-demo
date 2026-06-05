---
applyTo: "**/*"
---

# Project Scope Instructions

This repository implements a small computer-vision demo for a booth setup.

## Core User Experience

A visitor places a business card or similar card on a table.
A top-down camera detects the card.
The horizontal card position controls a live ranking/progress bar.

## MVP Definition

The MVP is intentionally small:

```text
camera frame
  ↓
OpenCV card detection
  ↓
card center x-position
  ↓
normalized score 0.0 ... 1.0
  ↓
browser UI ranking bar
```

## Non-Goals

Do not implement these unless explicitly requested:

- ROS2 integration
- cloud services
- databases
- user accounts
- authentication
- multi-camera support
- ML training pipeline
- complex frontend framework
- production monitoring stack
- Kubernetes or container orchestration
- generic plugin architecture

## Demo Constraint

This is a demo, not a long-term product.

Always minimize:

- development time
- dependency count
- deployment complexity
- maintenance burden
- hardware assumptions

## Decision Rule

If there are multiple valid implementations, choose the simplest one that is stable and easy to debug.
