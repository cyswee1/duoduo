#!/usr/bin/env python3
"""Build a zip bundle for distributing the skill package."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


EXCLUDE_PARTS = {
    ".git",
    "__pycache__",
    ".DS_Store",
    "weekly-ai-report",
    "dist",
    "tests",
}

EXCLUDE_FILES = {
    "test-prompts.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ai-weekly-progress-report zip bundle.")
    parser.add_argument("skill_dir", help="Skill package directory.")
    parser.add_argument("output_zip", help="Output zip path.")
    return parser.parse_args()


def should_include(path: Path) -> bool:
    return (
        path.name not in EXCLUDE_FILES
        and not any(part in EXCLUDE_PARTS for part in path.parts)
        and not path.name.endswith(".pyc")
    )


def main() -> int:
    args = parse_args()
    root = Path(args.skill_dir).resolve()
    output = Path(args.output_zip).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file() and should_include(path.relative_to(root)):
                arcname = Path(root.name) / path.relative_to(root)
                zf.write(path, arcname.as_posix())
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
