# Prompt: Implement the Next State

Use this prompt when asking the agent to implement one state of the CV-Card-Demo state machine.

## Task

Implement the next state in the state machine.

## Instructions

- Read `.github/copilot-instructions.md`.
- Follow all files in `.github/instructions/`.
- Keep the implementation minimal and demo-focused.
- Do not add unnecessary dependencies.
- Do not introduce ROS2, Docker Compose, databases, or deep learning.
- Keep state transitions explicit and logged.
- Update health status.
- Add small manual test instructions.

## State to Implement

Replace this section with the target state:

```text
STATE_NAME = INIT_CAM
```

## Expected Output

The implementation should include:

- state class
- clear `enter`, `run`, `exit` behavior
- logging
- health updates
- transition conditions
- failure handling
- no speculative features
