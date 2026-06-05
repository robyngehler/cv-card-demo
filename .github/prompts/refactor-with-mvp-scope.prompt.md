# Prompt: Refactor With MVP Scope

Use this prompt when code becomes messy but the project must remain small.

## Task

Refactor the selected code while preserving the MVP scope.

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

Good refactor targets:

- huge functions
- duplicated config parsing
- unclear state transitions
- mixed UI/CV/camera responsibilities
- silent exception handling
- hard-coded values that belong in config

Bad refactor targets:

- working simple code that is already readable
- adding abstractions for hypothetical future hardware
- introducing plugin systems
- replacing vanilla JS with a frontend framework

## Output Format

Provide:

1. short summary
2. files changed
3. behavior preserved
4. manual test steps
