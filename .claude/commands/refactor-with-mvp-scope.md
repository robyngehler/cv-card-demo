---
description: Refactor code while strictly preserving the MVP scope
argument-hint: (optional) file/area to refactor
---

# Refactor With MVP Scope

Use when code becomes messy but the project must remain small. Refactor the
selected code while preserving the MVP scope.

$ARGUMENTS

If no target was given above, ask which file or area to refactor.

## Rules

- Do not change behavior unless necessary.
- Do not introduce new dependencies.
- Do not create a generic framework.
- Split only where it improves readability.
- Keep public interfaces small.
- Preserve existing config keys when possible.
- Preserve state names and transition semantics.
- Add or improve logging only where useful.
- Keep WLED optional.

## Preferred Refactor Targets

Good: huge functions, duplicated config parsing, unclear state transitions,
mixed UI/CV/camera responsibilities, silent exception handling, hard-coded values
that belong in config.

Bad: working simple code that is already readable, abstractions for hypothetical
future hardware, plugin systems, replacing vanilla JS with a frontend framework.

## Output Format

1. short summary
2. files changed
3. behavior preserved
4. manual test steps
