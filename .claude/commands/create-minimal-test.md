---
description: Add the smallest useful test or diagnostic script for a module
argument-hint: (optional) module/file to test
---

# Create a Minimal Test

Create the smallest useful test for the selected module.

$ARGUMENTS

If no module was given above, ask which module to test.

## Rules

- Prefer simple unit tests or diagnostic scripts.
- Avoid large test frameworks if not already present.
- Do not require physical hardware unless testing a hardware service.
- For camera code, allow a mocked frame source where practical.
- For UI code, test health endpoints before browser automation.
- For WLED, test disabled/offline behavior first — WLED is optional.

## Output Format

1. what the test covers
2. how to run it
3. expected output
4. limitations
