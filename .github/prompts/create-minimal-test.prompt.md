# Prompt: Create a Minimal Test

Use this prompt to add a small test or diagnostic script.

## Task

Create the smallest useful test for the selected module.

## Rules

- Prefer simple unit tests or diagnostic scripts.
- Avoid large test frameworks if not already present.
- Do not require physical hardware unless testing a hardware service.
- For camera code, allow a mocked frame source where practical.
- For UI code, test health endpoints before browser automation.
- For WLED, test disabled/offline behavior first because WLED is optional.

## Output Format

Provide:

1. what the test covers
2. how to run it
3. expected output
4. limitations
