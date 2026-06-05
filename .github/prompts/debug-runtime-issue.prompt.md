# Prompt: Debug a Runtime Issue

Use this prompt when the booth demo fails during boot, camera initialization, UI startup, or tracking.

## Task

Analyze the runtime issue and propose the smallest safe fix.

## Required Context

Provide:

- current state
- logs
- command output
- config snippet
- observed behavior
- expected behavior

## Instructions for the Agent

- Keep the fix minimal.
- Do not redesign the architecture.
- Do not add new frameworks.
- Prefer explicit logging and health status improvements.
- Separate backend, UI, camera, and optional WLED issues.
- Remember that WLED is optional.
- If camera fails, route through `INIT_CAM` or `RECOVERY`.
- If UI fails, treat it as critical for the MVP.
- If backend crashes, ensure systemd recovery remains valid.

## Output Format

Respond with:

1. likely cause
2. evidence from logs/config
3. minimal fix
4. test command
5. rollback note if needed
