---
description: Analyze a runtime failure and propose the smallest safe fix
argument-hint: (optional) short description of the failure
---

# Debug a Runtime Issue

Use when the booth demo fails during boot, camera initialization, UI startup, or
tracking.

$ARGUMENTS

## Required Context

If not already provided, ask me for: current state, logs, command output, a
config snippet, observed behavior, and expected behavior. Useful commands:

```bash
journalctl -u cv-card-demo-backend.service -f
journalctl -u cv-card-demo-kiosk.service -f
systemctl status cv-card-demo-backend.service
```

## Instructions

- Keep the fix minimal. Do not redesign the architecture or add frameworks.
- Prefer explicit logging and health-status improvements.
- Separate backend, UI, camera, and optional WLED issues.
- Remember WLED is optional — it must not block the demo.
- If the camera fails, route through `INIT_CAM` or `RECOVERY`.
- If the UI fails, treat it as critical for the MVP.
- If the backend crashes, ensure systemd recovery remains valid.

## Output Format

1. likely cause
2. evidence from logs/config
3. minimal fix
4. test command
5. rollback note if needed

If the fix changes behavior or resolves a known issue, note the
`docs/sub-sprint-phase/<phase>/errors_and_fixes.md` update.
