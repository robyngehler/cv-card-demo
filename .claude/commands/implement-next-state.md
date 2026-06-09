---
description: Implement one state of the CV-Card-Demo state machine
argument-hint: <STATE_NAME>  e.g. INIT_CAM
---

# Implement the Next State

Implement the next state in the CV-Card-Demo state machine.

## State to Implement

```text
STATE_NAME = $ARGUMENTS
```

If no state name was given above, ask which state to implement before starting.

## Instructions

- The root `CLAUDE.md` and the nested `CLAUDE.md` files (especially
  `app/CLAUDE.md` and `app/states/CLAUDE.md`) are already loaded as project
  memory — follow them.
- Keep the implementation minimal and demo-focused.
- Do not add unnecessary dependencies.
- Do not introduce ROS2, Docker Compose, container orchestration, cloud APIs, or
  complex frontend frameworks.
- The existing stack already includes SQLite, YOLO, PaddleOCR, and Qdrant —
  use those existing services rather than introducing new storage or ML systems.
- Keep state transitions explicit and logged.
- Update health status.
- Add small manual test instructions.

## Expected Output

The implementation should include:

- the state class
- clear `enter`, `run`, `exit` behavior
- logging
- health updates
- transition conditions
- failure handling
- no speculative features

After implementing, update the relevant docs (`docs/sub-sprint-phase/<phase>/`
and, if a phase status changed, `docs/global_checklist.md`).
