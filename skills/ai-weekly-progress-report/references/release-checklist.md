# Release Checklist

Before publishing this skill to GitHub or sharing it with teammates:

- `SKILL.md` frontmatter has `name` and `description`.
- `agents/openai.yaml` uses the `interface` shape and mentions `$ai-weekly-progress-report` in `default_prompt`.
- `test-prompts.json` parses and includes happy path, no Git, missing roster, and privacy scenarios.
- `scripts/validate_skill_package.py .` passes.
- `tests/run_smoke.sh` passes on macOS/Linux.
- `README.md`, `VERSION`, and `CHANGELOG.md` are updated.
- The bundle was built with `scripts/build_bundle.py`.
- No local output folder, secrets, cache files, or machine-specific sample paths are included in the bundle.
