# CV-Card-Demo — Claude Code Instruction Template

This template ports the original GitHub Copilot instructions/prompts to a
Claude Code-native layout for use inside VS Code (Claude Code extension).

## What maps to what

| Original (Copilot)                          | This template (Claude Code)            |
|---------------------------------------------|----------------------------------------|
| `.github/copilot-instructions.md`           | `CLAUDE.md` (root, always in context)  |
| `00-project-scope`, `01-hardware-software`  | merged into root `CLAUDE.md`           |
| `02-architecture` (`app/**/*.py`)           | `app/CLAUDE.md`                        |
| `03-state-machine` + `04-boot-initcam`      | `app/states/CLAUDE.md`                 |
| `05-cv-pipeline` (`app/cv/**`)              | `app/cv/CLAUDE.md`                     |
| `06-ui-service` (service part)              | `app/services/CLAUDE.md`               |
| `06-ui-service` (web part)                  | `app/web/CLAUDE.md`                    |
| `08-wled-optional` (service / config)       | `app/services/CLAUDE.md` + `config/CLAUDE.md` |
| `07-systemd-deployment`                     | `systemd/CLAUDE.md` + `scripts/CLAUDE.md` |
| `09-progress-documentation`                 | `docs/CLAUDE.md` (+ root reminder)     |
| `*.prompt.md` files                         | `.claude/commands/*.md` slash commands |

## How Claude Code uses these

- The root `CLAUDE.md` is loaded into every session.
- Each nested `CLAUDE.md` loads automatically when Claude reads/edits files in
  that directory — this replaces Copilot's `applyTo:` globs.
- Prompts become slash commands: `/implement-next-state`, `/debug-runtime-issue`,
  `/create-minimal-test`, `/refactor-with-mvp-scope`.

## Layout

```text
CLAUDE.md
.claude/commands/
app/CLAUDE.md
app/states/CLAUDE.md
app/cv/CLAUDE.md
app/services/CLAUDE.md
app/web/CLAUDE.md
config/CLAUDE.md
systemd/CLAUDE.md
scripts/CLAUDE.md
docs/CLAUDE.md
docs/global_checklist.md
docs/sub-sprint-phase/_template/
```

Drop this into the root of your repository. The `app/`, `config/`, `systemd/`,
`scripts/` folders currently hold only their `CLAUDE.md` guides — add your code
into them as you build.
