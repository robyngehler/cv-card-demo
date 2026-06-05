---
applyTo: "**/*"
---

# Progress and Error Documentation Instructions

## Goal

The project must keep lightweight documentation of implementation progress, open tasks, known issues, and fixes.

This is a small demo project, so documentation must stay practical and minimal.
Do not create heavy project-management overhead.

The documentation exists to help humans and coding agents understand:

- what has already been implemented
- what is currently being worked on
- which errors occurred
- how errors were fixed
- what still needs to be done
- whether the global MVP plan is still on track

## Required Documentation Structure

Use the following structure:

```text
docs/
├── global_checklist.md
└── sub-sprint-phase/
    ├── README.md
    ├── _template/
    │   ├── checklist.md
    │   └── errors_and_fixes.md
    ├── 01_boot/
    │   ├── checklist.md
    │   └── errors_and_fixes.md
    ├── 02_init_cam/
    │   ├── checklist.md
    │   └── errors_and_fixes.md
    └── ...
```

## Global Checklist

The global checklist tracks the complete MVP plan.

Location:

```text
docs/global_checklist.md
```

It should contain:

- high-level project phases
- current status per phase
- acceptance criteria
- known blockers
- next recommended step

The global checklist is not a detailed task dump.
It is the organizational overview for the full demo.

## Sub-Sprint Phase Documentation

Each implementation phase must have its own folder below:

```text
docs/sub-sprint-phase/
```

Example:

```text
docs/sub-sprint-phase/01_boot/
docs/sub-sprint-phase/02_init_cam/
docs/sub-sprint-phase/03_ui_service/
docs/sub-sprint-phase/04_card_detection/
```

Each phase folder must contain:

```text
checklist.md
errors_and_fixes.md
```

## Phase Checklist

Each phase checklist must document:

- goal of the phase
- scope
- non-goals
- tasks
- acceptance criteria
- manual test steps
- current status

The checklist should use Markdown checkboxes:

```markdown
- [ ] Not started
- [x] Done
```

## Errors and Fixes

Each phase must maintain an error log:

```text
errors_and_fixes.md
```

Every relevant issue should be documented with:

- date
- context
- observed behavior
- expected behavior
- suspected cause
- fix applied
- verification step
- current status

Keep it short, but useful.

## When to Update Documentation

Update documentation whenever:

- a phase is started
- a task is completed
- a state transition is implemented
- a manual test was performed
- an error occurred
- a fix was applied
- an implementation decision changed
- a workaround was introduced
- a phase is considered complete

## Agent Responsibilities

When an agent changes implementation code, it should also check whether one of these files needs an update:

```text
docs/global_checklist.md
docs/sub-sprint-phase/<phase>/checklist.md
docs/sub-sprint-phase/<phase>/errors_and_fixes.md
```

If a code change completes a task, update the corresponding checklist.

If a code change fixes an issue, update `errors_and_fixes.md`.

If a code change affects the overall roadmap, update `docs/global_checklist.md`.

## Documentation Style

Keep documentation:

- short
- factual
- implementation-oriented
- easy to scan
- free of unnecessary theory

Avoid:

- long essays
- duplicate explanations
- speculative planning
- corporate project-management fluff
- excessive process overhead

This is a demo. The documentation should help the demo work, not become the demo.

## Status Labels

Use these status labels consistently:

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
DEFERRED
OPTIONAL
```

## Completion Rule

A phase is only considered `DONE` when:

1. implementation is complete
2. acceptance criteria are checked
3. manual test steps are documented
4. known errors are documented or explicitly marked as none
5. `docs/global_checklist.md` has been updated
