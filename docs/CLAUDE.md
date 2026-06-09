# Progress & Error Documentation — `docs/`

*Applies under `docs/`. The cross-cutting "update docs when you change code" rule
lives in the root `CLAUDE.md`.*

## Goal

Keep lightweight documentation of implementation progress, open tasks, known
issues, and fixes. This is a small demo — documentation stays practical and
minimal. No heavy project-management overhead.

The docs help humans and coding agents understand: what is implemented, what is
in progress, which errors occurred, how they were fixed, what remains, and
whether the MVP plan is on track.

## Structure

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

## Global Checklist (`global_checklist.md`)

The organizational overview for the full demo: high-level phases, current status
per phase, acceptance criteria, known blockers, next recommended step. Not a
detailed task dump.

## Phase Checklist (`checklist.md`)

Each phase documents: goal, scope, non-goals, tasks, acceptance criteria, manual
test steps, current status. Use Markdown checkboxes:

```markdown
- [ ] Not started
- [x] Done
```

## Errors and Fixes (`errors_and_fixes.md`)

Each relevant issue: date, context, observed behavior, expected behavior,
suspected cause, fix applied, verification step, current status. Short but useful.

## When to Update

Update docs whenever: a phase starts, a task completes, a state transition is
implemented, a manual test is performed, an error occurs, a fix is applied, a
decision changes, a workaround is introduced, or a phase is complete.

When you change code, check whether to update:

```text
docs/global_checklist.md
docs/sub-sprint-phase/<phase>/checklist.md
docs/sub-sprint-phase/<phase>/errors_and_fixes.md
```

## Style

Keep it short, factual, implementation-oriented, easy to scan. Avoid long essays,
duplicate explanations, speculative planning, and corporate fluff. The
documentation should help the demo work, not become the demo.

## Status Labels

```text
NOT_STARTED
IN_PROGRESS
BLOCKED
DONE
DEFERRED
OPTIONAL
```

## Completion Rule

A phase is `DONE` only when: implementation is complete, acceptance criteria are
checked, manual test steps are documented, known errors are documented (or marked
as none), and `docs/global_checklist.md` has been updated.
