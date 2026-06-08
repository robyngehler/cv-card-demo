# Sub-Sprint Phase Documentation

This folder contains lightweight documentation for each implementation phase.

Each phase should have its own folder:

```text
docs/sub-sprint-phase/01_boot/
docs/sub-sprint-phase/02_init_cam/
docs/sub-sprint-phase/03_workspace_calibration/
docs/sub-sprint-phase/04_card_detection/
docs/sub-sprint-phase/06_tracking_stability/
docs/sub-sprint-phase/07_tracking_advances/
docs/sub-sprint-phase/08_state_and_persistence_advances/
```

Each phase folder must contain:

```text
target.md
checklist.md
errors_and_fixes.md
```

Use `_template/` when creating a new phase folder.

---

## Required Files per Phase

### `target.md`

Tracks:

- objective scope for the sprint or phase
- guardrails that override older assumptions
- implementation target and current implementation status
- explicit out-of-scope items

### `checklist.md`

Tracks:

- phase goal
- scope
- non-goals
- tasks
- acceptance criteria
- manual tests
- current status

### `errors_and_fixes.md`

Tracks:

- errors encountered
- suspected causes
- fixes applied
- verification steps
- remaining issues

---

## Rule for Agents

Whenever implementation code changes, check whether the phase documentation must be updated.

Code without updated progress documentation is considered incomplete for this project.
