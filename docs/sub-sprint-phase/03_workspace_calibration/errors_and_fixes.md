# Errors and Fixes – 03 Workspace Calibration

This file documents workspace-calibration issues, failures, workarounds, and fixes for the `CALIBRATION` phase.

---

## Status

```text
IN_PROGRESS
```

---

## Active Issues

| Date | Issue | Status | Notes |
|---|---|---|---|
| TBD | No workspace calibration implemented yet | OPEN | Phase has not started in code |

---

## Error Entry Template

```markdown
## <YYYY-MM-DD> – <Short Error Title>

### Context

- state: `CALIBRATION`
- service: `workspace_service`
- command: `python -m app.main --config config/config.yaml --initial-state BOOT`

### Observed Behavior

What happened?

### Expected Behavior

What should have happened?

### Logs / Evidence

```text
paste short relevant log excerpt here
```

### Suspected Cause

Short factual explanation.

### Fix Applied

What was changed?

### Verification

Command:

```bash
# command here
```

Expected/observed result:

```text
result here
```

### Status

Use one:

```text
OPEN
FIXED
WORKAROUND
DEFERRED
CANNOT_REPRODUCE
```
```
