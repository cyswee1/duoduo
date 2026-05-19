# Portability Guide

## Supported Targets

| Target | Install location | Notes |
|---|---|---|
| Codex on macOS/Linux | Configured Codex global skills directory, commonly `~/.codex/skills/` | `agents/openai.yaml` improves discovery but is not required. |
| Codex on Windows | Configured Codex global skills directory | Use `py -3` or `python` if `python3` is unavailable. |
| TRAE | TRAE configured global Skills directory | Core behavior lives in `SKILL.md`; Codex metadata can be ignored. |
| QClaw/OpenClaw-style tools | Configured global skills directory | If OpenClaw only schedules TRAE, install in TRAE first. |

## Path Rules

- Install this package in the tool-level reusable Skills directory, not inside a single project repository.
- Project repositories may keep the source package for maintenance and versioning, but the runnable install should live in the tool's global Skills directory.
- Use explicit `--project-root` paths for Git/project evidence.
- The collector auto-detects common local tool roots: `~/.codex`, `~/.qclaw`, `~/.trae`, `~/.trae-cn`, `~/.claude`, and common Claude Desktop support directories.
- Use `--tool-root` for other AI tool roots that are not auto-detected.
- Do not hard-code one employee's absolute paths in shared examples.
- Preserve this package's relative directories after copying or unzipping.
- Before confirming a report, run the safe root preflight and check whether the user provided only a narrow project directory. The preflight should suggest only common top-level working folders, never the whole home directory.

## Common Project Root Candidates

| Platform | Candidate roots |
|---|---|
| macOS/Linux | `~/Documents/Codex`, `~/Documents/trae-projects`, `~/Documents/projects` |
| Windows | `%USERPROFILE%\Documents\Codex`, `%USERPROFILE%\Documents\trae-projects`, `%USERPROFILE%\Documents\projects` |
| Windows + OneDrive | Equivalent `Documents\Codex`, `Documents\trae-projects`, or `Documents\projects` folders under the configured OneDrive directory |

Use additional roots only when they exist and contain recent AI/project evidence. Other employee-specific locations must be supplied explicitly with `--project-root`.

## Validation Commands

macOS/Linux:

```bash
python3 scripts/validate_skill_package.py .
python3 -m json.tool test-prompts.json
tests/run_smoke.sh
```

Windows PowerShell:

```powershell
py -3 scripts/validate_skill_package.py .
py -3 -m json.tool test-prompts.json
```

If `py -3` is unavailable, use `python`.
