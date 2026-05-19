#!/usr/bin/env python3
"""Lightweight validator for the AI weekly progress report skill package."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED = [
    "SKILL.md",
    "README.md",
    "VERSION",
    "CHANGELOG.md",
    "agents/openai.yaml",
    "references/report-rubric.md",
    "references/privacy-exclusions.md",
    "references/portability-guide.md",
    "references/release-checklist.md",
    "scripts/collect_ai_weekly_report.py",
    "scripts/build_bundle.py",
    "templates/weekly-report.md.j2",
]

PROMPT_FIELDS = {"id", "prompt", "mode_expected", "must_check", "must_not_do", "score_focus"}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors: list[str] = []

    for rel in REQUIRED:
        if not (root / rel).exists():
            errors.append(f"missing required file: {rel}")

    skill = read(root / "SKILL.md")
    if not re.search(r"^---\n.*?^---", skill, flags=re.S | re.M):
        errors.append("SKILL.md missing YAML frontmatter")
    for term in ("name: ai-weekly-progress-report", "description:", "## Run Context", "## Workflow", "## Validation"):
        if term not in skill:
            errors.append(f"SKILL.md missing required term: {term}")
    for rel in ("references/report-rubric.md", "references/privacy-exclusions.md", "references/portability-guide.md", "references/release-checklist.md"):
        if rel not in skill:
            errors.append(f"SKILL.md does not reference {rel}")

    openai_yaml = read(root / "agents/openai.yaml")
    for term in ("interface:", "display_name:", "short_description:", "default_prompt:", "$ai-weekly-progress-report"):
        if term not in openai_yaml:
            errors.append(f"agents/openai.yaml missing {term}")

    prompts_path = root / "test-prompts.json"
    if prompts_path.exists():
        try:
            prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
            if not isinstance(prompts, list) or len(prompts) < 4:
                errors.append("test-prompts.json must contain at least 4 regression cases")
            for index, item in enumerate(prompts, start=1):
                missing = PROMPT_FIELDS - set(item)
                if missing:
                    errors.append(f"test-prompts.json case {index} missing fields: {', '.join(sorted(missing))}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"test-prompts.json parse failed: {exc}")

    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "skill_dir": str(root)}, ensure_ascii=False, indent=2))
    return 0


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


if __name__ == "__main__":
    raise SystemExit(main())
