#!/usr/bin/env python3
"""Collect local evidence for a manager-facing weekly AI progress report.

The collector is intentionally read-only and dependency-free. It scans Git
metadata, local AI-tool index files, and skill folders, then writes:

- evidence.json
- weekly-ai-report.md
- weekly-ai-report.html
- weekly-ai-report.pdf when a local HTML-to-PDF engine is available
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PATH = SKILL_DIR / "templates" / "weekly-report.md.j2"

SENSITIVE_PARTS = (
    "token",
    "secret",
    "credential",
    "password",
    "private-key",
    "id_rsa",
    "id_ed25519",
)

EXCLUDED_NAMES = {
    ".git",
    ".cache",
    ".npm",
    ".pnpm-store",
    ".venv",
    ".next",
    ".nuxt",
    "__pycache__",
    "node_modules",
    "vendor",
    "venv",
    "dist",
    "build",
    "target",
    "coverage",
    "auth.json",
    "credentials.json",
    "secrets.json",
    "weekly-ai-report",
    "weekly-ai-report.md",
    "weekly-ai-report.html",
    "weekly-ai-report.pdf",
    "leader-supplement-guide.md",
    "evidence.json",
    "run",
    "dist",
}

AI_KEYWORDS = (
    "ai",
    "agent",
    "codex",
    "trae",
    "qclaw",
    "skill",
    "skills",
    "rule",
    "rules",
    "mcp",
    "prompt",
    "automation",
    "自动化",
    "智能",
    "模型",
    "大模型",
    "工作流",
    "周报",
    "方法论",
    "知识库",
    "蒸馏",
    "爬取",
    "抓取",
    "问答",
)

METHODOLOGY_HINTS = (
    "skill",
    "skills",
    "rule",
    "rules",
    "prompt",
    "mcp",
    "template",
    "workflow",
    "方法",
    "模板",
)

COGNITION_HINTS = (
    "学习",
    "认知",
    "理解",
    "框架",
    "培训",
    "调研",
    "探索",
    "知识",
)

DELIVERY_HINTS = (
    "fix",
    "feat",
    "deploy",
    "test",
    "实现",
    "开发",
    "上线",
    "修复",
    "脚本",
    "项目",
)

ALLOWED_PROJECT_SUFFIXES = {
    ".md",
    ".py",
    ".html",
    ".json",
    ".jsonl",
    ".csv",
    ".ipynb",
    ".xlsx",
    ".xls",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}

TEXT_PROJECT_SUFFIXES = {
    ".md",
    ".py",
    ".html",
    ".json",
    ".jsonl",
    ".csv",
    ".ipynb",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}

SAFE_REPORT_ARTIFACT_NAMES = {
    "weekly-ai-report.md",
    "leader-supplement-guide.md",
    "skill-improvement-notes.md",
}

GENERATED_REPORT_NAMES = {
    "evidence.json",
    "leader-supplement-guide.md",
    "weekly-ai-report.md",
    "weekly-ai-report.html",
    "weekly-ai-report.pdf",
    "weekly-ai-report-roster.yaml",
}
GENERATED_REPORT_PREFIXES = (
    "weekly-ai-report",
    "ai-weekly-report",
    "ai-growth-business-practice-report",
    "growth-report",
    "leader-supplement-guide",
)

DATA_ANALYSIS_KEYWORDS = (
    "data",
    "analysis",
    "analytics",
    "dashboard",
    "report",
    "weekly",
    "monthly",
    "excel",
    "csv",
    "xlsx",
    "数据",
    "分析",
    "报表",
    "看板",
    "统计",
    "明细",
    "周报",
    "月报",
    "复盘",
)

GENERIC_PROJECT_KEYWORDS = (
    "project",
    "workflow",
    "pipeline",
    "automation",
    "dashboard",
    "report",
    "analysis",
    "scraper",
    "crawler",
    "archive",
    "extract",
    "transform",
    "skill",
    "prompt",
    "项目",
    "流程",
    "工作流",
    "自动化",
    "脚本",
    "报表",
    "报告",
    "分析",
    "看板",
    "爬虫",
    "抓取",
    "采集",
    "归档",
    "知识",
    "内容",
    "素材",
    "运营",
    "投放",
    "复盘",
)

REPORT_PACKAGE_NAME = "ai-weekly-progress-report"
REPORT_PACKAGE_RUNTIME_DIRS = {
    "agents",
    "dist",
    "references",
    "scripts",
    "templates",
    "tests",
}
REPORT_PACKAGE_RUNTIME_FILES = {
    "CHANGELOG.md",
    "README.md",
    "SKILL.md",
    "VERSION",
    "test-prompts.json",
}

TOOL_ROOT_NAMES = {
    ".codex",
    ".qclaw",
    ".trae",
    ".trae-cn",
    ".claude",
}

TOOL_INTERNAL_DIRS = {
    ".auto-memory",
    "agents",
    "backups",
    "devices",
    "logs",
    "plugins",
    "qmemory",
    "sync",
}

TOOL_INTERNAL_FILES = {
    ".consolidate-state.json",
    "config-audit.jsonl",
    "config-cache.json",
    "config-health.json",
    "models.json",
    "openclaw.json",
    "qclaw.json",
    "sessions.json",
    "skill-usage.json",
    "workspace-state.json",
}

WORKSPACE_MEMORY_FILES = {
    "IDENTITY.md",
    "MEMORY.md",
    "SOUL.md",
}

# Default team reports use generic evidence classification.
# Author-specific project maps were intentionally removed from the distributable
# collector to prevent cross-user leakage.

SKILL_TAG_STYLE = "color:#1f4ea8;font-style:italic;font-weight:650;"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect evidence and generate an AI weekly progress report draft."
    )
    parser.add_argument("--project-root", action="append", default=[], help="Git/project root to scan. Can be repeated.")
    parser.add_argument("--tool-root", action="append", default=[], help="AI tool root to scan. Can be repeated.")
    parser.add_argument("--team-roster", help="Leader/team YAML path. The members field is optional and ignored by the report template.")
    parser.add_argument("--leader", help="Reporting leader name. Overrides saved profile and roster leader.")
    parser.add_argument("--team", help="Team name. Overrides saved profile and roster team.")
    parser.add_argument("--profile", default=str(Path.home() / ".ai-weekly-progress-report" / "profile.json"), help="Local reporter profile path.")
    parser.add_argument("--remember-profile", action="store_true", help="Save leader/team to the profile path for future runs.")
    parser.add_argument("--since-days", type=int, default=14, help="Lookback window in days. Default: 14.")
    parser.add_argument("--output-dir", default="./weekly-ai-report", help="Output directory.")
    parser.add_argument("--max-sessions", type=int, default=80, help="Maximum AI session index rows to keep.")
    parser.add_argument("--max-commits", type=int, default=120, help="Maximum Git commits per repo to keep.")
    parser.add_argument("--max-project-files", type=int, default=3000, help="Maximum project file evidence rows to keep after diversity ranking. Increase for very large workspaces.")
    parser.add_argument("--suggest-roots-only", action="store_true", help="Only print safe top-level project root suggestions and exit.")
    return parser.parse_args()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: str) -> dt.datetime | None:
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def is_sensitive(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if name.startswith(".env"):
        return True
    if any(part in EXCLUDED_NAMES for part in parts):
        return True
    return any(marker in part for part in parts for marker in SENSITIVE_PARTS)


def is_safe_report_artifact(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return path.name in SAFE_REPORT_ARTIFACT_NAMES and "weekly-ai-report" in parts


def is_generated_report_artifact(path: Path) -> bool:
    name = path.name.lower()
    if name in GENERATED_REPORT_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in GENERATED_REPORT_PREFIXES):
        return True
    for part in path.parts:
        lower = part.lower()
        if any(lower.startswith(prefix) for prefix in GENERATED_REPORT_PREFIXES):
            return True
    return False


def is_report_package_artifact(value: Any) -> bool:
    """Exclude this skill package's own docs/tests from report evidence.

    Team users often install or unzip the skill package under a scanned top-level
    directory. The package contains regression prompts and examples with project
    names that are useful for QA but must never become a user's weekly progress.
    """
    text = str(value or "")
    normalized = text.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if REPORT_PACKAGE_NAME not in parts:
        path = Path(text).expanduser()
        package_root = nearest_report_package_root(path)
        if package_root is None:
            return False
        try:
            tail_path = path.resolve().relative_to(package_root)
            tail = [part.lower() for part in tail_path.parts]
        except (OSError, ValueError):
            tail = []
        if not tail:
            return True
        first = tail[0]
        last = tail[-1]
        return first in REPORT_PACKAGE_RUNTIME_DIRS or last in {name.lower() for name in REPORT_PACKAGE_RUNTIME_FILES}
    index = len(parts) - 1 - parts[::-1].index(REPORT_PACKAGE_NAME)
    tail = parts[index + 1 :]
    if not tail:
        return True
    first = tail[0]
    last = tail[-1]
    return first in REPORT_PACKAGE_RUNTIME_DIRS or last in {name.lower() for name in REPORT_PACKAGE_RUNTIME_FILES}


def is_installed_tool_skill_artifact(value: Any) -> bool:
    """Exclude globally installed tool skills from project evidence.

    A tool root such as ~/.qclaw can contain real workspace artifacts, but its
    `skills/` folder is an installed capability library. Those files may contain
    third-party descriptions or package QA examples and must not become the
    reporter's weekly achievements.
    """
    normalized = str(value or "").replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    for index, part in enumerate(parts[:-1]):
        if part in TOOL_ROOT_NAMES and parts[index + 1] == "skills":
            return True
    return False


def is_tool_internal_nonproject_artifact(value: Any) -> bool:
    """Exclude tool state, memory, session, and config files from project evidence."""
    normalized = str(value or "").replace("\\", "/")
    lower = normalized.lower()
    parts = [part for part in lower.split("/") if part]
    original_parts = [part for part in normalized.split("/") if part]
    for index, part in enumerate(parts):
        if part not in TOOL_ROOT_NAMES:
            continue
        tail = parts[index + 1 :]
        original_tail = original_parts[index + 1 :]
        if not tail:
            return False
        if tail[0] in TOOL_INTERNAL_DIRS:
            return True
        if tail[0] == "skills":
            return True
        if tail[-1] in TOOL_INTERNAL_FILES:
            return True
        if tail[0].startswith("workspace") and len(tail) > 1:
            if tail[1] in {"memory", ".openclaw"}:
                return True
            if original_tail[-1] in WORKSPACE_MEMORY_FILES:
                return True
        return False
    return False


def nearest_report_package_root(path: Path) -> Path | None:
    try:
        current = path.resolve()
    except OSError:
        current = path.absolute()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        skill_file = candidate / "SKILL.md"
        if not skill_file.exists() or is_sensitive(skill_file):
            continue
        try:
            head = skill_file.read_text(encoding="utf-8", errors="ignore")[:600]
        except OSError:
            continue
        if f"name: {REPORT_PACKAGE_NAME}" in head:
            return candidate
    return None


def safe_resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def default_project_root_candidates() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Documents" / "Codex",
        home / "Documents" / "trae-projects",
        home / "Documents" / "projects",
    ]
    if os.name == "nt":
        for env_name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
            one_drive = os.environ.get(env_name)
            if one_drive:
                base = Path(one_drive) / "Documents"
                candidates.extend([base / "Codex", base / "trae-projects", base / "projects"])
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser()
        try:
            resolved = resolved.resolve()
        except OSError:
            resolved = candidate.expanduser().absolute()
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def is_under_any(path: Path, roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def build_root_preflight(project_roots: list[str], cutoff: dt.datetime) -> dict[str, Any]:
    scanned: list[Path] = []
    for root in project_roots:
        resolved = safe_resolve(root)
        if resolved.exists() and not is_sensitive(resolved):
            scanned.append(resolved)

    suggestions: list[dict[str, Any]] = []
    for candidate in default_project_root_candidates():
        if not candidate.exists() or is_sensitive(candidate) or is_under_any(candidate, scanned):
            continue
        signal_files = collect_project_files([str(candidate)], cutoff, limit=12)
        if not signal_files:
            continue
        suggestions.append(
            {
                "path": str(candidate),
                "signal_count": len(signal_files),
                "signals": [
                    {
                        "path": item.get("path", ""),
                        "matched_terms": item.get("matched_terms", [])[:6],
                    }
                    for item in signal_files[:6]
                ],
            }
        )

    return {
        "scanned_roots": [str(path) for path in scanned],
        "suggested_roots": suggestions,
        "note": "Safe top-level candidates only; no broad home-directory scan.",
    }


def run(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, 124, exc.stdout or "", exc.stderr or f"Timed out after {timeout}s")


def load_roster(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise SystemExit(f"Team roster not found: {path}")
    text = path.read_text(encoding="utf-8")
    data = parse_minimal_yaml(text)
    members = data.get("members") or []
    for index, member in enumerate(members, start=1):
        if not member.get("name"):
            raise SystemExit(f"Roster member #{index} is missing name.")
        member.setdefault("role", "")
    return data


def load_profile(path: Path) -> dict[str, str]:
    if not path.exists() or is_sensitive(path):
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {key: str(value) for key, value in data.items() if key in {"leader", "team"}}


def save_profile(path: Path, roster: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"leader": roster.get("leader", ""), "team": roster.get("team", "")}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_roster(args: argparse.Namespace) -> dict[str, Any]:
    roster_path = safe_resolve(args.team_roster) if args.team_roster else None
    roster = load_roster(roster_path)
    profile_path = safe_resolve(args.profile)
    profile = load_profile(profile_path)
    leader = args.leader or roster.get("leader") or profile.get("leader")
    team = args.team or roster.get("team") or profile.get("team")
    if not leader or not team:
        raise SystemExit("Missing leader/team. Provide --leader and --team once, or use --team-roster, then optionally --remember-profile.")
    roster["leader"] = leader
    roster["team"] = team
    roster.setdefault("members", [])
    if args.remember_profile:
        save_profile(profile_path, roster)
    return roster


def parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Parse the small roster YAML shape without requiring PyYAML."""
    data: dict[str, Any] = {}
    members: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_members = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^\s*members\s*:\s*$", line):
            in_members = True
            continue
        if not in_members and ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = strip_yaml_value(value)
            continue
        if in_members:
            stripped = line.strip()
            if stripped.startswith("- "):
                if current:
                    members.append(current)
                current = {}
                item = stripped[2:].strip()
                if item and ":" in item:
                    key, value = item.split(":", 1)
                    current[key.strip()] = strip_yaml_value(value)
                continue
            if current is not None and ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = strip_yaml_value(value)

    if current:
        members.append(current)
    if members:
        data["members"] = members
    return data


def strip_yaml_value(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def discover_tool_roots(extra_roots: list[str]) -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        Path.home() / ".codex",
        Path.home() / ".qclaw",
        Path.home() / ".trae",
        Path.home() / ".trae-cn",
        Path.home() / ".claude",
        Path.home() / "Library" / "Application Support" / "Claude",
        Path.home() / "Library" / "Application Support" / "Claude-3p",
    ):
        if candidate.exists() and not is_sensitive(candidate):
            roots.append(candidate.resolve())
    for root in extra_roots:
        resolved = safe_resolve(root)
        if resolved.exists() and resolved not in roots and not is_sensitive(resolved):
            roots.append(resolved)
    return roots


def collect_git(project_roots: list[str], cutoff: dt.datetime, max_commits: int) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    seen: set[Path] = set()

    for root in project_roots:
        path = safe_resolve(root)
        if not path.exists() or is_sensitive(path):
            continue
        if is_report_package_artifact(path):
            continue
        repo = git_root(path)
        if not repo or repo in seen or is_sensitive(repo) or is_report_package_artifact(repo):
            continue
        seen.add(repo)
        commits = git_commits(repo, cutoff, max_commits)
        repos.append(
            {
                "path": str(repo),
                "commit_count": len(commits),
                "commits": commits,
                "ai_related_commits": [c for c in commits if looks_ai_related(c["subject"] + " " + " ".join(c["files"]))],
            }
        )
    return repos


def collect_project_files(project_roots: list[str], cutoff: dt.datetime, limit: int = 200) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in project_roots:
        path = safe_resolve(root)
        if not path.exists() or is_sensitive(path):
            continue
        scan_root = path if path.is_dir() else path.parent
        for file_path in scan_root.rglob("*"):
            if not file_path.is_file() or file_path in seen:
                continue
            if is_generated_report_artifact(file_path):
                continue
            if is_report_package_artifact(file_path):
                continue
            if is_installed_tool_skill_artifact(file_path):
                continue
            if is_tool_internal_nonproject_artifact(file_path):
                continue
            if is_sensitive(file_path):
                continue
            if file_path.suffix.lower() not in ALLOWED_PROJECT_SUFFIXES and file_path.name != "SKILL.md":
                continue
            try:
                stat = file_path.stat()
            except OSError:
                continue
            modified = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
            if modified < cutoff:
                continue
            rel_text = str(file_path)
            sample = ""
            if should_read_sample(file_path):
                try:
                    sample = file_path.read_text(encoding="utf-8", errors="ignore")[:4000]
                except OSError:
                    sample = ""
            related_text = rel_text + " " + sample
            if not looks_reportable_project_file(file_path, related_text):
                continue
            seen.add(file_path)
            files.append(
                {
                    "path": str(file_path),
                    "modified_at": modified.isoformat(),
                    "category": categorize_project_file(file_path, related_text),
                    "kind": classify_project_file(file_path, related_text),
                    "matched_terms": matched_terms(related_text),
                }
            )
    return select_project_file_evidence(files, limit)


def select_project_file_evidence(files: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Keep project evidence broad instead of letting one large folder dominate.

    The collector may scan a top-level workspace such as ~/Documents/Codex where
    one active project can contain hundreds of generated scripts or reports. A
    first-come limit hides later projects, so rank all candidates first and use a
    diversity pass before filling the remaining capacity.
    """
    if limit <= 0 or len(files) <= limit:
        return sorted(files, key=project_file_sort_key, reverse=True)

    target_groups = max(1, len({project_file_group_key(item) for item in files}))
    per_group_soft_cap = max(40, min(180, limit // max(1, min(target_groups, 12))))
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in files:
        groups.setdefault(project_file_group_key(item), []).append(item)
    for group_items in groups.values():
        group_items.sort(key=project_file_sort_key, reverse=True)

    selected: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    def add_item(item: dict[str, Any]) -> None:
        path = str(item.get("path", ""))
        if path and path not in seen_paths and len(selected) < limit:
            selected.append(item)
            seen_paths.add(path)

    for _, group_items in sorted(groups.items(), key=lambda pair: len(pair[1]), reverse=True):
        for item in group_items[:per_group_soft_cap]:
            add_item(item)

    if len(selected) < limit:
        for item in sorted(files, key=project_file_sort_key, reverse=True):
            add_item(item)

    return selected


def project_file_group_key(item: dict[str, Any]) -> str:
    path = Path(str(item.get("path", "")))
    parts = path.parts
    for anchor in ("Codex", "trae-projects", "projects"):
        if anchor in parts:
            index = parts.index(anchor)
            tail = parts[index + 1 :]
            if not tail:
                return str(path.parent)
            if tail[0] in {"projects", "project"} and len(tail) > 1:
                return "/".join(tail[:2])
            if tail[0] == "SEO-master" and len(tail) > 1:
                return "/".join(tail[:2])
            return tail[0]
    return str(path.parent)


def project_file_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    kind_rank = {
        "custom_skill": 6,
        "script": 5,
        "data_analysis": 4,
        "document": 3,
        "file": 2,
    }.get(str(item.get("kind", "")), 1)
    category_bonus = 1 if str(item.get("category", "")) in {"data_analysis", "methodology", "delivery"} else 0
    return (kind_rank + category_bonus, str(item.get("modified_at", "")))


def should_read_sample(file_path: Path) -> bool:
    return file_path.name == "SKILL.md" or file_path.suffix.lower() in TEXT_PROJECT_SUFFIXES


def looks_data_analysis_related(text: str) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in DATA_ANALYSIS_KEYWORDS)


def is_project_skill_file(file_path: Path) -> bool:
    return file_path.name == "SKILL.md" and not is_report_package_artifact(file_path)


def looks_reportable_project_file(file_path: Path, text: str) -> bool:
    if is_project_skill_file(file_path):
        return True
    if looks_ai_related(text) or looks_project_related(text):
        return True
    if looks_data_analysis_related(text):
        return True
    return False


def classify_project_file(file_path: Path, text: str) -> str:
    suffix = file_path.suffix.lower()
    if is_project_skill_file(file_path):
        return "custom_skill"
    if suffix in {".py", ".ipynb"}:
        return "script"
    if suffix in {".csv", ".xlsx", ".xls"} or looks_data_analysis_related(text):
        return "data_analysis"
    if suffix in {".html", ".md"}:
        return "document"
    return "file"


def categorize_project_file(file_path: Path, text: str) -> str:
    kind = classify_project_file(file_path, text)
    if kind == "data_analysis":
        return "data_analysis"
    if kind == "custom_skill":
        return "methodology"
    return categorize_text(text)


def git_root(path: Path) -> Path | None:
    proc = run(["git", "rev-parse", "--show-toplevel"], cwd=path if path.is_dir() else path.parent)
    if proc.returncode != 0:
        return None
    root = Path(proc.stdout.strip()).resolve()
    return root if root.exists() else None


def git_commits(repo: Path, cutoff: dt.datetime, max_commits: int) -> list[dict[str, Any]]:
    since = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    fmt = "%H%x1f%an%x1f%aI%x1f%s"
    proc = run(["git", "log", f"--since={since}", f"--pretty=format:{fmt}", f"-n{max_commits}"], cwd=repo)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    commits: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        commit_hash, author, authored_at, subject = parts
        files = git_commit_files(repo, commit_hash)
        commits.append(
            {
                "hash": commit_hash[:12],
                "author": author,
                "authored_at": authored_at,
                "subject": subject,
                "files": files,
                "category": categorize_text(subject + " " + " ".join(files)),
            }
        )
    return commits


def git_commit_files(repo: Path, commit_hash: str) -> list[str]:
    proc = run(["git", "show", "--name-only", "--pretty=format:", commit_hash], cwd=repo)
    if proc.returncode != 0:
        return []
    files: list[str] = []
    for raw in proc.stdout.splitlines():
        item = raw.strip()
        if item and not is_sensitive(Path(item)) and not is_report_package_artifact(repo / item):
            files.append(item)
    return files[:30]


def collect_tools(tool_roots: list[Path], cutoff: dt.datetime, max_sessions: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for root in tool_roots:
        if is_sensitive(root) or is_report_package_artifact(root):
            continue
        sessions = collect_session_index(root, cutoff, max_sessions)
        skills = collect_skill_assets(root, cutoff)
        results.append(
            {
                "path": str(root),
                "session_count": len(sessions),
                "sessions": sessions,
                "skill_asset_count": len(skills),
                "skill_assets": skills,
            }
        )
    return results


def collect_session_index(root: Path, cutoff: dt.datetime, max_sessions: int) -> list[dict[str, Any]]:
    index_path = root / "session_index.jsonl"
    if not index_path.exists() or is_sensitive(index_path):
        return []
    sessions: list[dict[str, Any]] = []
    try:
        lines = index_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        updated = parse_time(str(obj.get("updated_at", "")))
        if updated and updated < cutoff:
            continue
        title = str(obj.get("thread_name") or obj.get("name") or "").strip()
        if not title:
            continue
        title_related = looks_ai_related(title) or looks_project_related(title)
        if len(sessions) >= max_sessions and not title_related:
            continue
        session_id = str(obj.get("id", ""))
        deep = collect_session_deep_signals(root, session_id)
        terms = matched_terms(title + " " + " ".join(deep.get("matched_terms", [])) + " " + " ".join(deep.get("project_mentions", [])))
        if len(sessions) >= max_sessions * 2:
            break
        sessions.append(
            {
                "id": session_id[:16],
                "title": title,
                "updated_at": obj.get("updated_at", ""),
                "category": categorize_text(title + " " + " ".join(terms)),
                "ai_related": title_related or bool(deep.get("matched_terms")),
                "matched_terms": terms,
                "session_path": deep.get("session_path", ""),
                "project_mentions": deep.get("project_mentions", [])[:12],
            }
        )
    return sessions


def collect_session_deep_signals(root: Path, session_id: str) -> dict[str, Any]:
    if not session_id:
        return {}
    matches: list[Path] = []
    sessions_dir = root / "sessions"
    if sessions_dir.exists() and not is_sensitive(sessions_dir):
        matches.extend(sessions_dir.glob(f"**/*{session_id}*.jsonl"))
    archived_dir = root / "archived_sessions"
    if archived_dir.exists() and not is_sensitive(archived_dir):
        matches.extend(archived_dir.glob(f"**/*{session_id}*.jsonl"))
    if not matches:
        return {}
    path = matches[0]
    if is_sensitive(path):
        return {}
    text_parts: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return {}
    for line in lines[:600]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = obj.get("payload", {})
        if obj.get("type") == "event_msg" and payload.get("type") in {"user_message", "agent_message"}:
            text_parts.append(str(payload.get("message", "")))
        if obj.get("type") == "response_item":
            item_type = payload.get("type")
            if item_type == "message":
                for content in payload.get("content", []) or []:
                    if isinstance(content, dict):
                        text_parts.append(str(content.get("text") or content.get("input_text") or content.get("output_text") or ""))
            elif item_type == "function_call":
                text_parts.append(str(payload.get("arguments", "")))
    haystack = "\n".join(text_parts)
    matched = matched_terms(haystack)
    project_mentions = extract_project_mentions(haystack)
    return {
        "matched_terms": matched,
        "project_mentions": project_mentions,
        "session_path": str(path) if matched or project_mentions else "",
    }


def extract_project_mentions(text: str) -> list[str]:
    """Extract local project/file path hints from session text without storing chat text."""
    mentions: list[str] = []
    patterns = [
        r"/Users/[^\s'\"`<>]+/Documents/Codex/[^\s'\"`<>]+",
        r"~/Documents/Codex/[^\s'\"`<>]+",
        r"/Users/[^\s'\"`<>]+/Documents/trae-projects/[^\s'\"`<>]+",
        r"~/Documents/trae-projects/[^\s'\"`<>]+",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, text):
            cleaned = raw.rstrip(".,;:，。；：)）]】")
            if not cleaned or is_sensitive(Path(cleaned.replace("~", str(Path.home()), 1))):
                continue
            if is_report_package_artifact(cleaned):
                continue
            mentions.append(cleaned)
            if len(mentions) >= 30:
                return sorted(set(mentions))
    return sorted(set(mentions))


def collect_skill_assets(root: Path, cutoff: dt.datetime) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for skills_dir in (root / "skills", root / "vendor_imports" / "skills", root / "workspace" / "skills"):
        if not skills_dir.exists() or is_sensitive(skills_dir):
            continue
        for skill_file in skills_dir.rglob("SKILL.md"):
            skill_dir = skill_file.parent
            if skill_dir in seen or is_sensitive(skill_file):
                continue
            seen.add(skill_dir)
            try:
                modified = dt.datetime.fromtimestamp(skill_file.stat().st_mtime, tz=dt.timezone.utc)
            except OSError:
                continue
            metadata = read_skill_metadata(skill_file)
            name = metadata.get("name") or skill_dir.name
            assets.append(
                {
                    "name": name,
                    "path": str(skill_dir),
                    "modified_at": modified.isoformat(),
                    "in_window": modified >= cutoff,
                    "description": metadata.get("description", ""),
                    "category": "methodology",
                }
            )
    assets.sort(key=lambda item: (not item.get("in_window"), str(item.get("name", "")).lower()))
    return assets[:300]


def read_skill_metadata(skill_file: Path) -> dict[str, str]:
    try:
        text = skill_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    metadata: dict[str, str] = {}
    lines = parts[1].splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index]
        if ":" not in raw:
            index += 1
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        if key in {"name", "description"}:
            value = strip_yaml_value(value)
            if key == "description" and value in {">", "|", ">-", "|-"}:
                folded: list[str] = []
                index += 1
                while index < len(lines):
                    continuation = lines[index]
                    if continuation and not continuation.startswith((" ", "\t")) and ":" in continuation:
                        index -= 1
                        break
                    folded.append(continuation.strip())
                    index += 1
                metadata[key] = " ".join(part for part in folded if part)
            else:
                metadata[key] = value
        index += 1
    return metadata


def looks_ai_related(text: str) -> bool:
    lower = text.lower()
    return any(keyword.lower() in lower for keyword in AI_KEYWORDS)


def looks_project_related(text: str) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in GENERIC_PROJECT_KEYWORDS)


def matched_terms(text: str) -> list[str]:
    lower = text.lower()
    terms = [keyword for keyword in AI_KEYWORDS if keyword.lower() in lower]
    for keyword in DATA_ANALYSIS_KEYWORDS:
        if keyword.lower() in lower and keyword not in terms:
            terms.append(keyword)
    for keyword in GENERIC_PROJECT_KEYWORDS:
        if keyword.lower() in lower and keyword not in terms:
            terms.append(keyword)
    return sorted(set(terms), key=lambda item: item.lower())[:20]


def categorize_text(text: str) -> str:
    lower = text.lower()
    if looks_data_analysis_related(text):
        return "data_analysis"
    if any(hint.lower() in lower for hint in METHODOLOGY_HINTS):
        return "methodology"
    if any(hint.lower() in lower for hint in COGNITION_HINTS):
        return "cognition"
    if any(hint.lower() in lower for hint in DELIVERY_HINTS):
        return "delivery"
    if looks_ai_related(lower):
        return "ai_related"
    return "general"


def summarize(evidence: dict[str, Any], roster: dict[str, Any]) -> dict[str, str]:
    git_repos = evidence["git_repositories"]
    tools = evidence["tool_roots"]
    project_files = evidence.get("project_files", [])
    project_root_count = len(evidence.get("inputs", {}).get("project_roots", []))
    ai_commits = [c for repo in git_repos for c in repo.get("ai_related_commits", [])]
    all_commits = [c for repo in git_repos for c in repo.get("commits", [])]
    sessions = [s for tool in tools for s in tool.get("sessions", [])]
    skills = [s for tool in tools for s in tool.get("skill_assets", [])]
    initiatives = build_initiatives(evidence)
    projects = build_project_level_projects(evidence)
    if initiatives and (all_commits or sessions or project_files):
        evidence_status = "需人工确认"
    elif all_commits or sessions or project_files:
        evidence_status = "线索待归因"
    else:
        evidence_status = "主要靠补充"

    progress_items = build_progress_output_items(initiatives, all_commits, project_files)

    executive = render_executive_summary(progress_items, tools, project_files)

    return {
        "scanned_projects": str(project_root_count or len(git_repos)),
        "scanned_tools": str(len(tools)),
        "initiative_count": str(len(initiatives)),
        "evidence_status": evidence_status,
        "supplement_status": "待主管确认本周进度产出和下周计划",
        "root_preflight": render_root_preflight(evidence.get("root_preflight", {})),
        "executive_summary": executive,
        "progress_output": render_progress_output(progress_items, "请补充本周实际进度、业务产出、工具/工作流沉淀、文档/脚本/HTML/PDF/dashboard 等可交付物；如无补充，请确认无补充。"),
        "project_level_progress": render_project_level_output(projects),
        "next_steps": "- 下周计划：待主管补充。\n- 风险与待支持：待主管补充。",
        "evidence_summary": render_evidence_summary(git_repos, tools, project_files, initiatives, projects, evidence.get("root_preflight", {})),
    }


def build_project_level_projects(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Build neutral project candidates from strong local evidence.

    Default team reports must not depend on the package author's project map.
    This groups concrete files and commits by their local project folder, then
    uses generic category language. Installed skills and session-title-only
    matches stay out of default project synthesis.
    """
    project_roots = [safe_resolve(path) for path in evidence.get("inputs", {}).get("project_roots", []) if str(path).strip()]
    groups: dict[str, dict[str, Any]] = {}

    def ensure_group(key: str, title: str) -> dict[str, Any]:
        group = groups.setdefault(
            key,
            {
                "key": key,
                "title": title,
                "source_labels": {"commit": [], "project": [], "session": []},
                "kinds": [],
                "terms": [],
            },
        )
        if title and group.get("title", "").startswith("项目推进：未归类"):
            group["title"] = title
        return group

    for file_item in evidence.get("project_files", []):
        path_text = str(file_item.get("path", ""))
        if not path_text or is_report_package_artifact(path_text):
            continue
        if is_installed_tool_skill_artifact(path_text):
            continue
        if is_tool_internal_nonproject_artifact(path_text):
            continue
        path = Path(path_text)
        key, title = infer_project_group(path, project_roots)
        group = ensure_group(key, title)
        label = short_path(path_text)
        if label not in group["source_labels"]["project"]:
            group["source_labels"]["project"].append(label)
        group["kinds"].append(str(file_item.get("kind", "file")))
        group["terms"].extend(str(term) for term in file_item.get("matched_terms", []))

    for repo in evidence.get("git_repositories", []):
        repo_path = Path(str(repo.get("path", "")))
        for commit in repo.get("commits", []):
            files = [str(file_name) for file_name in commit.get("files", []) if str(file_name).strip()]
            if not files and not looks_ai_related(str(commit.get("subject", ""))):
                continue
            if is_report_package_artifact(" ".join([str(repo_path), str(commit.get("subject", "")), *files])):
                continue
            first_file = repo_path / files[0] if files else repo_path
            key, title = infer_project_group(first_file, [repo_path, *project_roots])
            group = ensure_group(key, title)
            label = str(commit.get("subject", "")).strip() or short_path(first_file)
            if label not in group["source_labels"]["commit"]:
                group["source_labels"]["commit"].append(label)
            group["kinds"].append(str(commit.get("category", "delivery")))
            group["terms"].extend(matched_terms(" ".join([str(commit.get("subject", "")), *files])))

    for tool in evidence.get("tool_roots", []):
        for session in tool.get("sessions", []):
            mentions = [str(item) for item in session.get("project_mentions", []) if str(item).strip()]
            if not mentions:
                continue
            label = str(session.get("title", "")).strip() or str(session.get("id", "")).strip()
            for mention in mentions[:8]:
                if is_report_package_artifact(mention):
                    continue
                key, title = infer_project_group(Path(mention).expanduser(), project_roots)
                group = ensure_group(key, title)
                if label and label not in group["source_labels"]["session"]:
                    group["source_labels"]["session"].append(label)
                group["kinds"].append(str(session.get("category", "session")))
                group["terms"].extend(str(term) for term in session.get("matched_terms", []))

    projects: list[dict[str, Any]] = []
    for group in groups.values():
        source_labels = group["source_labels"]
        if not source_labels["project"] and not source_labels["commit"]:
            continue
        confidence = project_confidence(
            [source for source, labels in source_labels.items() if labels],
            list({term for term in group["terms"] if term}),
        )
        goal = generic_project_goal(group)
        project = {
            "id": group["key"],
            "title": group["title"],
            "goal": goal,
            "confidence": confidence,
            "sources": [source for source, labels in source_labels.items() if labels],
            "evidence_labels": source_labels,
            "text": render_generic_project_level_item(group, goal, confidence),
        }
        projects.append(project)

    projects.sort(key=lambda item: project_sort_key(item), reverse=True)
    return projects[:6]


def infer_project_group(path: Path, project_roots: list[Path]) -> tuple[str, str]:
    tool_group = infer_tool_path_group_name(str(path))
    if tool_group:
        tool_name, name = tool_group
        key = f"{tool_name}:{name}".lower()
        return key, f"项目推进：{humanize_project_name(name)}"
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    for root in project_roots:
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            break
        if root.name.lower() in TOOL_ROOT_NAMES and parts[0].lower().startswith("workspace"):
            name = infer_workspace_project_name(parts, root.name)
        elif parts[0] in {"projects", "project"} and len(parts) > 1:
            name = parts[1]
        elif re.fullmatch(r"20\d{2}-\d{2}-\d{2}", parts[0]) and len(parts) > 1:
            name = parts[1]
        elif len(parts) == 1:
            name = root.name or parts[0]
        elif parts[0].lower() in {"src", "scripts", "docs", "reports", "data", "outputs", "assets", "skills"}:
            name = parts[1] if len(parts) > 2 else root.name
        else:
            name = parts[0]
        key = f"{root}:{name}".lower()
        return key, f"项目推进：{humanize_project_name(name)}"
    name = resolved.parent.name if resolved.suffix else resolved.name
    return str(resolved.parent).lower(), f"项目推进：{humanize_project_name(name)}"


def infer_workspace_project_name(parts: tuple[str, ...], fallback: str) -> str:
    if len(parts) > 2 and parts[1] not in {"memory", ".openclaw"}:
        return parts[1]
    if len(parts) > 1:
        stem = Path(parts[-1]).stem.lower()
        for marker in ("smartbi", "scrm", "weisheng", "waiqu", "excel", "bi"):
            if marker in stem:
                return marker
        return stem or fallback
    return fallback


def infer_tool_path_group_name(value: str) -> tuple[str, str] | None:
    normalized = str(value or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    for index, part in enumerate(parts):
        if part.lower() not in TOOL_ROOT_NAMES:
            continue
        tail = tuple(parts[index + 1 :])
        if not tail:
            return None
        if tail[0].lower().startswith("workspace"):
            return part, infer_workspace_project_name(tail, part)
        if tail[0].lower() == "media" and len(tail) > 1:
            stem = Path(tail[-1]).stem
            return part, stem or tail[1]
        return None
    return None


def humanize_project_name(name: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", str(name)).strip()
    return cleaned or "未归类项目"


def generic_project_goal(group: dict[str, Any]) -> str:
    kinds = set(group.get("kinds", []))
    title_context = str(group.get("title", "")).lower()
    context = project_context_text(group)
    terms = " ".join(str(term) for term in group.get("terms", [])).lower()
    if any(term in title_context for term in ("seo", "meta", "facebook", "ads")):
        return "把投放、SEO 和平台知识整理为可查询、可复用的增长运营知识资产。"
    if any(term in title_context for term in ("知识学习", "xmp", "help center")):
        return "把外部资料采集、归档和知识整理流程沉淀为可复用的学习与知识库建设方法。"
    if any(term in title_context for term in ("video creator", "内容创作")):
        return "把内容素材、提示词组织和视频生成流程沉淀为可复用的内容生产方法。"
    if "date solution" in title_context:
        return "把外呼、分期、成本清洗和业务复盘流程整理为可复核的数据运营方法。"
    if "数据分析" in title_context:
        return "把业务数据、分析口径和报表需求整理为可复核、可交接的分析交付流程。"
    if any(term in context for term in ("date solution", "外呼", "aftee", "分期", "供应商", "成本", "号码", "出站")):
        return "把外呼、分期、成本清洗和业务复盘流程整理为可复核的数据运营方法。"
    if any(term in context for term in ("video creator", "内容创作", "seedance", "gpt image", "storyboard", "prompt", "素材", "视频", "短片", "分镜")):
        return "把内容素材、提示词组织和视频生成流程沉淀为可复用的内容生产方法。"
    if any(term in context for term in ("数据分析", "api_requirements", "报表", "分析", "xlsx", "csv", "看板")):
        return "把业务数据、分析口径和报表需求整理为可复核、可交接的分析交付流程。"
    if "custom_skill" in kinds:
        return "把项目内可重复的操作、判断或交付流程沉淀为本地可复用 Skill / 工作流资产。"
    if "data_analysis" in kinds or any(term in terms for term in ("数据", "分析", "报表", "dashboard", "csv", "xlsx")):
        return "把数据处理、分析结论或报表产物整理为可复核、可复用的业务分析流程。"
    if "script" in kinds or any(term in terms for term in ("脚本", "自动化", "爬虫", "抓取", "crawler", "scraper")):
        return "把重复性采集、处理或生成任务推进为脚本化、自动化的项目能力。"
    if any(term in terms for term in ("内容", "素材", "prompt", "提示词", "storyboard", "image")):
        return "把内容、素材或提示词生产整理为可复盘、可交接的项目工作流。"
    return "把近周期分散文件、提交和工作线索归并为可确认的项目级推进。"


def render_generic_project_level_item(group: dict[str, Any], goal: str, confidence: str) -> str:
    title = group.get("title", "项目推进：未归类项目")
    description, value = project_business_copy(group, goal)
    return (
        f"| **{escape_pipe(str(title))}** | "
        f"{escape_pipe(description)} | "
        f"{escape_pipe(value)} |"
    )


def project_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    labels = item.get("evidence_labels", {})
    commit_count = len(labels.get("commit", []))
    project_count = len(labels.get("project", []))
    confidence_rank = {"高": 3, "中": 2, "待确认": 1}.get(str(item.get("confidence")), 0)
    return (confidence_rank, commit_count + project_count, project_count)


def render_root_preflight(root_preflight: dict[str, Any]) -> str:
    scanned = [short_path(path) for path in root_preflight.get("scanned_roots", [])]
    suggestions = root_preflight.get("suggested_roots", [])
    lines = [
        f"- 已扫描目录：{', '.join(scanned) if scanned else '未提供项目根目录'}",
    ]
    if not suggestions:
        lines.append("- 建议补扫目录：未发现安全顶级候选目录中存在明显近周期 AI 项目线索。")
        lines.append("- 可能漏掉的项目线索：暂无。")
        return "\n".join(lines)
    lines.append("- 建议补扫目录：" + "、".join(short_path(item.get("path", "")) for item in suggestions[:5]))
    signal_parts: list[str] = []
    for item in suggestions[:3]:
        root = short_path(item.get("path", ""))
        terms: list[str] = []
        for signal in item.get("signals", [])[:3]:
            terms.extend(str(term) for term in signal.get("matched_terms", [])[:4])
        term_text = "、".join(sorted(set(terms), key=str.lower)[:8]) or "近周期项目文件"
        signal_parts.append(f"{root}（{term_text}）")
    lines.append("- 可能漏掉的项目线索：" + "；".join(signal_parts))
    return "\n".join(lines)


def project_confidence(active_sources: list[str], hits: list[str]) -> str:
    source_set = set(active_sources)
    if "commit" in source_set or {"project", "session"}.issubset(source_set):
        return "高"
    if "project" in source_set or len(hits) >= 3:
        return "中"
    return "待确认"


def passes_specific_trigger(pattern: dict[str, Any], hits: list[str]) -> bool:
    return True


def render_project_level_item(pattern: dict[str, Any], confidence: str, source_labels: dict[str, list[str]]) -> str:
    description = project_description_statement(pattern["goal"])
    value = project_value_statement(pattern["goal"])
    return (
        f"| **{escape_pipe(str(pattern['title']))}** | "
        f"{escape_pipe(description)} | "
        f"{escape_pipe(value)} |"
    )


def project_context_text(group: dict[str, Any]) -> str:
    labels: list[str] = [str(group.get("title", ""))]
    labels.extend(str(term) for term in group.get("terms", []))
    source_labels = group.get("source_labels", {})
    for source in ("commit", "project", "session"):
        labels.extend(str(label) for label in source_labels.get(source, [])[:8])
    return " ".join(labels).lower()


def project_business_copy(group: dict[str, Any], goal: str) -> tuple[str, str]:
    title_context = str(group.get("title", "")).lower()
    context = project_context_text(group)
    if any(term in title_context for term in ("seo", "meta", "facebook", "ads")):
        return (
            "围绕投放、SEO 和平台规则知识，建立可查询、可更新、可复用的增长运营知识资产。",
            "降低平台知识分散带来的判断成本，提升投放诊断、SEO 优化和跨项目增长支持的响应效率。",
        )
    if any(term in title_context for term in ("知识学习", "xmp", "help center")):
        return (
            "围绕外部资料采集、文章归档和知识蒸馏流程，建立从资料获取到结构化复用的知识生产链路。",
            "让高价值资料从一次性阅读转化为可检索、可复盘、可继续加工的知识资产，支撑培训、研究和业务问答。",
        )
    if any(term in title_context for term in ("video creator", "内容创作")):
        return (
            "围绕内容创作、提示词组织和视频生成流程，沉淀从素材理解到产物生成的可复用方法。",
            "提升内容生产的稳定性和可复制性，减少创作流程对单次对话和个人经验的依赖，便于复用到营销素材、培训内容和业务说明场景。",
        )
    if "date solution" in title_context:
        return (
            "围绕外呼、分期、成本清洗和业务复盘流程，沉淀数据处理、异常判断和复盘交付方法。",
            "帮助业务团队更快统一数据口径、定位流程问题和识别供应商表现差异，提升复盘效率和后续决策质量。",
        )
    if "数据分析" in title_context:
        return (
            "围绕业务数据、分析口径和报表需求，整理可复核、可交接的分析交付流程。",
            "提升数据复盘的可靠性和管理可读性，帮助团队更快判断业务问题、优先级和后续投入方向。",
        )
    if any(term in context for term in ("date solution", "外呼", "aftee", "分期", "供应商", "成本", "号码", "出站")):
        return (
            "围绕外呼、分期、成本清洗和业务复盘流程，沉淀数据处理、异常判断和复盘交付方法。",
            "帮助业务团队更快统一数据口径、定位流程问题和识别供应商表现差异，提升复盘效率和后续决策质量。",
        )
    if any(term in context for term in ("video creator", "内容创作", "seedance", "gpt image", "storyboard", "prompt", "素材", "视频", "短片", "分镜")):
        return (
            "围绕内容创作、提示词组织和视频生成流程，沉淀从素材理解到产物生成的可复用方法。",
            "提升内容生产的稳定性和可复制性，减少创作流程对单次对话和个人经验的依赖，便于复用到营销素材、培训内容和业务说明场景。",
        )
    if any(term in context for term in ("数据分析", "api_requirements", "报表", "分析", "xlsx", "csv", "看板")):
        return (
            "围绕业务数据、分析口径和报表需求，整理可复核、可交接的分析交付流程。",
            "提升数据复盘的可靠性和管理可读性，帮助团队更快判断业务问题、优先级和后续投入方向。",
        )
    return project_description_statement(goal), project_value_statement(goal)


def project_value_statement(goal: str) -> str:
    text = str(goal).strip()
    if not text:
        return "把分散工作沉淀成可复盘、可交接、可继续投入的项目主线，降低后续重复判断和重复执行成本。"
    return text.rstrip("。") + "，降低重复沟通、重复判断和重复执行成本，提升后续复用和交接效率。"


def project_description_statement(goal: str) -> str:
    text = str(goal).strip().rstrip("。")
    if not text:
        return "围绕一个可持续推进的业务或管理主题，把分散任务整理成可复盘、可交接、可继续投入的项目方向。"
    if "Skill" in text or "工作流" in text or "操作" in text or "判断" in text or "交付流程" in text:
        return "围绕重复操作、判断标准和交付步骤建设可复用工作流，使团队从一次性处理转向可持续复用的执行体系。"
    if any(term in text for term in ("数据", "分析", "报表", "看板")):
        return "围绕业务数据、分析口径和报表产物建立可复核的分析流程，让管理层能持续跟踪问题、结论和后续动作。"
    if any(term in text for term in ("脚本", "自动化", "采集", "处理", "生成")):
        return "围绕重复采集、处理和生成任务建设自动化能力，减少手工操作依赖并提升交付稳定性。"
    if any(term in text for term in ("内容", "素材", "提示词", "prompt", "storyboard", "image")):
        return "围绕内容素材和生成流程沉淀可复用生产方法，让创意产出从单次生成转向可复盘、可迭代的流程。"
    return f"围绕{text}形成项目化推进方向，把相关工作沉淀为可管理、可复盘、可继续投入的业务主线。"


def project_current_judgment(confidence: str) -> str:
    if confidence == "高":
        return "可进入正文候选；业务结果、使用对象和优先级仍需主管最终确认。"
    if confidence == "中":
        return "建议作为正文候选或合并项处理，取决于主管是否认可其业务价值。"
    return "默认放入附录观察，不进入正式项目成果。"


def compact_project_evidence(source_labels: dict[str, list[str]]) -> str:
    parts: list[str] = []
    source_names = {"commit": "Git", "project": "项目文件", "session": "会话"}
    for source in ("commit", "project", "session"):
        labels = [label for label in source_labels.get(source, []) if label][:3]
        if labels:
            parts.append(f"{source_names[source]}：{'、'.join(labels)}")
    return "；".join(parts) if parts else "本地线索不足，需主管确认"


def build_initiatives(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Synthesize generic weekly progress themes from concrete evidence.

    This intentionally avoids author-specific templates. It only turns strong
    project files or commits into neutral capability themes.
    """
    project_files = [
        item
        for item in evidence.get("project_files", [])
        if not is_report_package_artifact(item.get("path", ""))
        and not is_installed_tool_skill_artifact(item.get("path", ""))
        and not is_tool_internal_nonproject_artifact(item.get("path", ""))
    ]
    commits = [
        commit
        for repo in evidence.get("git_repositories", [])
        for commit in repo.get("commits", [])
        if not is_report_package_artifact(" ".join([commit.get("subject", ""), *commit.get("files", [])]))
    ]

    groups: dict[str, dict[str, Any]] = {
        "custom-skill-workflow": {
            "category": "methodology",
            "title": "可复用工作流资产沉淀",
            "capability": "将高频、重复、容易依赖个人经验的工作步骤整理成稳定执行入口，使后续同类任务可以按统一流程推进。",
            "value": "降低后续重复沟通和执行口径不一致的成本，便于团队复用、培训和交接。",
            "transfer": "可迁移到团队 SOP、知识库、自动化流程和跨项目复用。",
            "paths": [],
            "terms": [],
        },
        "data-reporting-workflow": {
            "category": "delivery",
            "title": "业务分析与报表产物整理",
            "capability": "围绕业务数据、分析口径和报表输出建立可复核的分析过程，让问题、结论和后续动作能够被持续追踪。",
            "value": "提升数据复盘的可靠性和可交接性，帮助管理层更快判断业务问题、优先级和后续投入方向。",
            "transfer": "可迁移到运营报表、财务核对、投放复盘、客服质检和业务监控。",
            "paths": [],
            "terms": [],
        },
        "script-automation": {
            "category": "delivery",
            "title": "脚本化与自动化能力建设",
            "capability": "将重复采集、清洗、生成和验证任务沉淀为可执行工具，减少对手工操作和口头流程的依赖。",
            "value": "减少手工操作和口头流程依赖，为后续稳定运行、排错和交接打基础。",
            "transfer": "可迁移到资料采集、数据处理、内容生产、报表生成和内部工具原型。",
            "paths": [],
            "terms": [],
        },
        "document-knowledge-output": {
            "category": "methodology",
            "title": "文档、知识资料与报告交付",
            "capability": "将阶段性判断、资料整理和业务说明沉淀为可阅读、可引用、可继续加工的交付物。",
            "value": "提升工作结果的可见度和复盘效率，减少关键判断只停留在对话中的风险。",
            "transfer": "可迁移到培训资料、项目复盘、业务说明、知识库和管理汇报。",
            "paths": [],
            "terms": [],
        },
    }

    for item in project_files:
        kind = item.get("kind")
        path = short_path(item.get("path", ""))
        terms = [str(term) for term in item.get("matched_terms", [])]
        if kind == "custom_skill":
            target = groups["custom-skill-workflow"]
        elif kind == "data_analysis":
            target = groups["data-reporting-workflow"]
        elif kind == "script":
            target = groups["script-automation"]
        else:
            target = groups["document-knowledge-output"]
        if path not in target["paths"]:
            target["paths"].append(path)
        target["terms"].extend(terms)

    for commit in commits:
        text = " ".join([commit.get("subject", ""), *commit.get("files", [])])
        terms = matched_terms(text)
        if not terms:
            continue
        target = groups["script-automation"] if commit.get("category") == "delivery" else groups["document-knowledge-output"]
        label = commit.get("subject", "")
        if label and label not in target["paths"]:
            target["paths"].append(label)
        target["terms"].extend(terms)

    initiatives: list[dict[str, Any]] = []
    for initiative_id, group in groups.items():
        if not group["paths"]:
            continue
        initiatives.append(
            {
                "id": initiative_id,
                "category": group["category"],
                "title": group["title"],
                "capability": group["capability"],
                "value": group["value"],
                "transfer": group["transfer"],
                "paths": list(group["paths"]),
                "hits": sorted(set(group["terms"]), key=str.lower)[:8],
                "sources": ["project"],
                "text": render_generic_initiative_item(group),
            }
        )
    return initiatives


def render_generic_initiative_item(group: dict[str, Any]) -> str:
    return (
        f"| **{escape_pipe(str(group['title']))}** | "
        f"{escape_pipe(str(group['capability']))} | "
        f"{escape_pipe(str(group['value']))} |"
    )


def render_initiative_item(pattern: dict[str, Any], hits: list[str]) -> str:
    skills = list(pattern.get("skills", ()))
    hit_text = "\n".join(str(hit) for hit in hits).lower()
    attribution_names = [skill for skill in skills if str(skill).lower() in hit_text]
    if not attribution_names:
        attribution_names = [hit for hit in hits if "-" in hit][:4]
    attribution = format_skill_tags(attribution_names) if attribution_names else "扫描关键词"
    evidence_source = "本地项目文件或 Git 证据命中：" + "、".join(hits[:6]) + "。"
    transfer = str(pattern.get("transfer", "可迁移到相似业务流程、团队协作和后续项目复用。"))
    return (
        f"- **{pattern['title']}**：扫描线索识别为该任务方向，本周期已形成可汇报的工作线索。"
        f"管理价值是{pattern['value']}\n"
        f"  - 能力：{pattern['capability']}\n"
        f"  - 来源：{evidence_source}\n"
        f"  - 迁移：{transfer}\n"
        f"  - 产出/归因：{attribution}"
    )


def render_executive_summary(progress_items: list[str], tools: list[dict[str, Any]], project_files: list[dict[str, Any]]) -> str:
    headlines: list[str] = []
    for item in progress_items:
        match = re.search(r"\*\*(.+?)\*\*", item)
        if match:
            headlines.append(match.group(1))

    evidence_text = "\n".join(progress_items + [str(file_item.get("path", "")) for file_item in project_files]).lower()
    lines: list[str] = []
    if not headlines and not project_files:
        return (
            "- 本周扫描线索不足以支撑明确总体判断，需结合主管补充确认实际进展。\n"
            "- 当前周报只保留可核对的项目、文件、会话和本机资产线索，避免把弱证据写成已完成成果。"
        )

    if "custom_skill" in evidence_text or "项目本地自定义 skill" in evidence_text or "工作流资产" in evidence_text:
        lines.append("- 高频重复任务开始沉淀为可复用工作流，团队后续可以围绕统一入口复盘、培训和交接。")
    elif any(term in evidence_text for term in ("工作流", "workflow", "自动化", "pipeline")):
        lines.append("- AI 使用方式开始从单点任务推进到流程化执行，后续更适合按流程复用、质量检查和持续迭代来管理。")
    if any(term in evidence_text for term in ("周报", "报告", "html", "pdf", "dashboard", "脚本", "交付")):
        lines.append("- 产出形态从对话结果进一步落到报告、脚本、HTML/PDF 或项目文件等可交付物，便于后续复盘、共享和团队协作。")
    if any(term in evidence_text for term in ("数据", "分析", "报表", "csv", "xlsx", "dashboard")):
        lines.append("- 数据分析和报表类产物开始承担业务复盘入口的作用，后续可围绕分析对象、关键结论和业务动作继续完善。")
    if not lines and headlines:
        lines.append(f"- 本周 AI 化进展主要集中在{'、'.join(headlines[:3])}，整体更偏向把零散实践整理成可核对、可复用的工作产出。")
    lines.append("- 正文聚焦管理层需要快速判断的业务主线，支撑材料统一放在附录中追溯。")
    return "\n".join(lines[:3])


def build_progress_output_items(
    initiatives: list[dict[str, Any]],
    commits: list[dict[str, Any]],
    project_files: list[dict[str, Any]],
) -> list[str]:
    items: list[str] = []
    items.extend([item["text"] for item in initiatives if item.get("category") in {"methodology", "delivery"}])
    if len(items) < 4:
        items.extend(select_commit_items(commits, "delivery", 4 - len(items)))
    if len(items) < 4:
        items.extend(select_file_items(project_files, "delivery", 4 - len(items)))
    if not items:
        items = select_commit_items(commits, "ai_related", 4)
    return items[:6]


def render_progress_output(items: list[str], prompt: str) -> str:
    if not items:
        return f"- {prompt}"
    table_rows = [item for item in items if item.lstrip().startswith("|")]
    if table_rows:
        return "\n".join(
            [
                "| 进展主线 | 项目描述 | 业务价值 |",
                "|---|---|---|",
                *table_rows[:6],
            ]
        )
    return "\n".join(items[:6])


def render_project_level_output(projects: list[dict[str, Any]]) -> str:
    rows = [str(item.get("text", "")) for item in projects if str(item.get("text", "")).lstrip().startswith("|")]
    if not rows:
        return "- 本周期未从本地资产中提取到稳定项目层级线索。"
    return "\n".join(
        [
            "| 项目主线 | 项目描述 | 业务价值 |",
            "|---|---|---|",
            *rows[:6],
        ]
    )

def skill_tag(name: str) -> str:
    safe_name = html.escape(str(name))
    return f'<span class="skill-name" style="{SKILL_TAG_STYLE}">{safe_name}</span>'


def format_skill_tags(names: list[str] | tuple[str, ...]) -> str:
    filtered = [str(name).strip() for name in names if str(name).strip()]
    return "、".join(skill_tag(name) for name in filtered)


def select_items(items: list[dict[str, Any]], category: str, key: str, limit: int) -> list[str]:
    selected = [item for item in items if item.get("category") == category]
    result: list[str] = []
    for item in selected[:limit]:
        evidence = item.get("path") or item.get("session_path") or item.get("updated_at", "")
        terms = item.get("matched_terms", [])
        term_text = f"；关键词：{', '.join(terms[:5])}" if terms else ""
        result.append(f"- {item.get(key, '')}（证据：{short_path(evidence)}{term_text}）")
    return result


def select_file_items(files: list[dict[str, Any]], category: str, limit: int) -> list[str]:
    selected = [
        item
        for item in files
        if item.get("kind") not in {"custom_skill", "data_analysis"}
        and (item.get("category") == category or item.get("matched_terms"))
    ]
    return [render_file_item(item) for item in selected[:limit]]


def select_priority_file_items(files: list[dict[str, Any]], kind: str, limit: int) -> list[str]:
    selected = [item for item in files if item.get("kind") == kind]
    return [render_file_item(item) for item in selected[:limit]]


def render_file_item(item: dict[str, Any]) -> str:
    path = short_path(item.get("path", ""))
    terms = "、".join(item.get("matched_terms", [])[:5]) or "近周期文件"
    kind = item.get("kind", "file")
    if kind == "custom_skill":
        return f"- **项目本地自定义 Skill / 工作流资产**：{path}（线索：{terms}；是否为本周新建或迭代需主管确认）"
    if kind == "data_analysis":
        return f"- **数据分析 / 报表产物线索**：{path}（线索：{terms}；可补充本周分析对象、结论和业务用途）"
    if kind == "script":
        return f"- **脚本 / 自动化文件线索**：{path}（关键词：{terms}）"
    return f"- 近期项目文件：{path}（关键词：{terms}）"


def select_commit_items(commits: list[dict[str, Any]], category: str, limit: int) -> list[str]:
    selected = [commit for commit in commits if commit.get("category") == category or category == "ai_related"]
    result: list[str] = []
    for commit in selected[:limit]:
        files = ", ".join(commit.get("files", [])[:3])
        suffix = f"；涉及：{files}" if files else ""
        result.append(f"- {commit.get('subject')}（{commit.get('author')}，{commit.get('hash')}{suffix}）")
    return result


def bullets_or_prompt(items: list[str], prompt: str) -> str:
    if items:
        return "\n".join(items[:10])
    return "- 本周期未从本地资产中提取到稳定线索。"


def render_evidence_summary(
    git_repos: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    project_files: list[dict[str, Any]],
    initiatives: list[dict[str, str]],
    projects: list[dict[str, Any]] | None = None,
    root_preflight: dict[str, Any] | None = None,
) -> str:
    rows = ["| 来源 | 线索数量 | 可信度 | 说明 |", "|---|---:|---|---|"]
    for repo in git_repos:
        confidence = "证据充分" if repo.get("commit_count") else "需人工确认"
        rows.append(f"| Git: `{escape_pipe(short_path(repo['path']))}` | {repo.get('commit_count', 0)} | {confidence} | commit 元数据和文件名，仅作项目进展线索 |")
    for tool in tools:
        count = tool.get("session_count", 0) + tool.get("skill_asset_count", 0)
        confidence = "需人工确认" if tool.get("session_count", 0) else "主要来自人工补充"
        rows.append(f"| Tool: `{escape_pipe(short_path(tool['path']))}` | {count} | {confidence} | 会话标题和 Skill 资产是线索，不直接等同成果 |")
    if project_files:
        rows.append(f"| Project files | {len(project_files)} | 需人工确认 | 非 Git 或未提交文件线索，用于补足工作区真实产出 |")
    if initiatives:
        rows.append(f"| Synthesized initiatives | {len(initiatives)} | 需人工确认 | 多证据合成的工作流级判断 |")
    if projects:
        rows.append(f"| Project-level candidates | {len(projects)} | 需人工确认 | 跨文件、会话和工作流归并的复杂项目候选 |")
    suggestions = (root_preflight or {}).get("suggested_roots", [])
    if suggestions:
        rows.append(f"| Suggested project roots | {len(suggestions)} | 需人工确认 | 安全顶级目录预检发现可能漏传的项目根目录 |")
    if len(rows) == 2:
        rows.append("| 无本地证据 | 0 | 主要来自人工补充 | 请主管逐模块确认 |")
    appendix = render_evidence_appendix(project_files, initiatives, projects)
    return "\n".join(rows + appendix)


def render_evidence_appendix(
    project_files: list[dict[str, Any]],
    initiatives: list[dict[str, Any]],
    projects: list[dict[str, Any]] | None,
) -> list[str]:
    lines: list[str] = []
    initiative_rows = render_initiative_evidence_rows(initiatives)
    project_rows = render_project_evidence_rows(projects or [])
    file_rows = render_file_evidence_rows(project_files)
    if initiative_rows:
        lines.extend(["", "### 进度主线证据明细（附录）", "", "| 主线 | 代表线索 | 说明 |", "|---|---|---|", *initiative_rows])
    if project_rows:
        lines.extend(["", "### 项目证据明细（附录）", "", "| 项目 | 证据类型 | 代表线索 | 可信度 |", "|---|---|---|---|", *project_rows])
    if file_rows:
        lines.extend(["", "### 其他候选文件线索（附录）", "", "| 类型 | 代表线索 | 说明 |", "|---|---|---|", *file_rows])
    return lines


def render_initiative_evidence_rows(initiatives: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for item in initiatives[:6]:
        labels = [short_path(path) for path in item.get("paths", [])[:3]]
        if not labels:
            continue
        rows.append(
            f"| {escape_pipe(str(item.get('title', '未命名主线')))} | {escape_pipe('；'.join(labels))} | 正文只呈现管理主线，具体归因在此追溯 |"
        )
    return rows


def render_project_evidence_rows(projects: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    source_names = {"commit": "Git", "project": "项目文件", "session": "会话"}
    for project in projects[:10]:
        labels = project.get("evidence_labels", {})
        source_types = "、".join(source_names[source] for source in ("commit", "project", "session") if labels.get(source))
        representative = compact_project_evidence(labels)
        rows.append(
            f"| {escape_pipe(str(project.get('title', '未命名项目')))} | {escape_pipe(source_types or '弱线索')} | {escape_pipe(representative)} | {escape_pipe(str(project.get('confidence', '待确认')))} |"
        )
    return rows


def render_file_evidence_rows(project_files: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for item in project_files[:12]:
        kind = str(item.get("kind", "file"))
        if kind in {"custom_skill", "data_analysis", "script"}:
            continue
        path = short_path(item.get("path", ""))
        terms = "、".join(str(term) for term in item.get("matched_terms", [])[:4]) or "近周期文件"
        rows.append(f"| {escape_pipe(kind)} | {escape_pipe(path)} | {escape_pipe(terms)} |")
    return rows[:6]


def short_path(value: Any) -> str:
    text = str(value or "")
    home = str(Path.home())
    if text.startswith(home):
        return "~" + text[len(home):]
    return text


def escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")


def render_markdown(template_values: dict[str, str], roster: dict[str, Any], cutoff: dt.datetime, now: dt.datetime) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "team": roster["team"],
        "leader": roster["leader"],
        "window_start": cutoff.astimezone().strftime("%Y-%m-%d"),
        "window_end": now.astimezone().strftime("%Y-%m-%d"),
        **template_values,
    }
    for key, value in values.items():
        template = template.replace("{{ " + key + " }}", str(value))
    return template


def render_supplement_guide(roster: dict[str, Any], summary: dict[str, str], preview_md_path: Path) -> str:
    root_preflight = summary.get("root_preflight", "").strip() or "- 已扫描目录：未提供项目根目录\n- 建议补扫目录：暂无。"
    progress_preview = summary.get("progress_output", "").strip() or "- 本周期未从本地资产中提取到稳定线索。"
    project_preview = summary.get("project_level_progress", "").strip() or "- 本周期未从本地资产中提取到稳定项目层级线索。"
    return f"""# AI 周进度汇报主管补充向导

汇报人：{roster.get('leader')}  
团队：{roster.get('team')}

请按顺序确认。周报正文采用“本周进度与产出 + 项目层级推进 + 下周计划”的结构；第一段和第二段的扫描总结正文不由填写人直接改写，只允许在对应段落下追加“自主说明”。

重要：确认动作只在本向导和对话流程中完成。最终 `weekly-ai-report.md` / `weekly-ai-report.html` / `weekly-ai-report.pdf` 不应出现 `[需主管确认]`、`[需主管补充]`、`请主管确认` 或每条成果后追加的确认说明。

## 第零步：扫描范围预检

正式确认正文前，先检查是否漏传顶级项目目录。若这里出现建议补扫目录，应优先补充 `--project-root` 后重新生成草稿；否则可能漏掉项目级动作。

```text
{root_preflight}
```

## 第一步：本周进度与产出

请先核对系统基于扫描结果生成的草稿。下方扫描总结结果为锁定原文，不允许填写人直接改写；如有未能识别、总结不准确或团队成员工作产出等信息，请写入“自主说明”。

当前预览文档：`{preview_md_path}`

### Skills 扫描与总结结果（原文锁定）

```text
{progress_preview}
```

### 自主说明

请检查内容，必要信息输入说明（如未能识别或总结不准确的内容；团队成员工作产出等）。

填写区：

```text
自主说明：
```

## 第二步：项目层级推进

请核对系统基于扫描结果生成的项目候选。下方扫描总结结果为锁定原文，不允许填写人直接改写；如有未能识别、总结不准确或团队成员工作产出等信息，请写入“自主说明”。

### Skills 扫描与总结结果（原文锁定）

```text
{project_preview}
```

### 自主说明

请检查内容，必要信息输入说明（如未能识别或总结不准确的内容；团队成员工作产出等）。

填写区：

```text
自主说明：
```

## 第三步：下周计划与协调事项

请按两个部分补充即可。若某部分没有内容，可写“暂无”。

```text
下周计划：
风险与待支持：
```

## 第四步：预览稿确认

补充确认完成后，生成 `weekly-ai-report.md`、`weekly-ai-report.html`，并在本机支持时生成 `weekly-ai-report.pdf`。请确认预览稿是否接受，或指出需要继续修改的模块。
"""


def render_html(markdown: str, title: str) -> str:
    body = markdown_to_html(markdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2933;
      --muted: #68717d;
      --line: #d9ded7;
      --paper: #fbfaf6;
      --accent: #9f4f2f;
      --soft: #f1eee7;
    }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: "PingFang SC", "Source Han Serif SC", "Noto Serif CJK SC", Georgia, serif;
      font-size: 17px;
      line-height: 1.78;
    }}
    main {{
      max-width: 820px;
      margin: 0 auto;
      padding: 52px 28px 72px;
    }}
    h1, h2, h3 {{
      line-height: 1.3;
      letter-spacing: 0;
      color: #18222d;
    }}
    h1 {{
      font-size: 2rem;
      margin: 0 0 1.2rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--line);
    }}
    h2 {{
      font-size: 1.35rem;
      margin: 2.2rem 0 0.8rem;
      color: var(--accent);
    }}
    h3 {{
      font-size: 1.05rem;
      margin: 1.4rem 0 0.5rem;
    }}
    p, ul, table {{
      margin: 0 0 1rem;
    }}
    blockquote {{
      margin: 1.2rem 0;
      padding: 0.85rem 1rem;
      border-left: 4px solid var(--accent);
      background: #f5f2ec;
      color: #39414a;
    }}
    ul {{
      padding-left: 1.3rem;
    }}
    li {{
      margin: 0.28rem 0;
    }}
    .li-level-1 {{
      margin-left: 1.4rem;
      list-style-type: circle;
    }}
    .li-level-2 {{
      margin-left: 2.8rem;
      list-style-type: square;
    }}
    .li-level-3 {{
      margin-left: 4.2rem;
      list-style-type: "- ";
    }}
    code {{
      font-family: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
      font-size: 0.9em;
      background: var(--soft);
      padding: 0.08rem 0.26rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.93rem;
      line-height: 1.55;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 0.5rem 0.45rem;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: #3d4650;
      background: #f4f1ea;
      font-weight: 650;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1px;
      background: var(--line);
      border: 1px solid var(--line);
      margin: 1.4rem 0;
    }}
    .kpi {{
      background: #fffdf8;
      padding: 0.95rem 1rem;
    }}
    .kpi-label {{
      font-size: 0.76rem;
      color: var(--muted);
      letter-spacing: 0.04em;
    }}
    .kpi-value {{
      font-size: 1.55rem;
      font-weight: 700;
      color: #18222d;
      margin-top: 0.15rem;
    }}
    .kpi-delta {{
      font-size: 0.82rem;
      color: var(--muted);
    }}
    .skill-name {{
      color: #1f4ea8;
      font-style: italic;
      font-weight: 650;
    }}
    @media (max-width: 640px) {{
      body {{ font-size: 16px; }}
      main {{ padding: 32px 18px 52px; }}
      h1 {{ font-size: 1.65rem; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    in_list = False
    in_table = False
    table_header_seen = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def close_table() -> None:
        nonlocal in_table, table_header_seen
        if in_table:
            out.append("</tbody></table>")
            in_table = False
            table_header_seen = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_list()
            close_table()
            continue
        if stripped.startswith("<") and stripped.endswith(">"):
            close_list()
            close_table()
            out.append(stripped)
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            close_list()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            if not in_table:
                out.append("<table><tbody>")
                in_table = True
                table_header_seen = False
            tag = "th" if not table_header_seen else "td"
            out.append("<tr>" + "".join(f"<{tag}>{inline_md(cell)}</{tag}>" for cell in cells) + "</tr>")
            table_header_seen = True
            continue
        close_table()
        if stripped.startswith("#"):
            close_list()
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            text = stripped[level:].strip()
            out.append(f"<h{level}>{inline_md(text)}</h{level}>")
        elif stripped.startswith("> "):
            close_list()
            out.append(f"<blockquote>{inline_md(stripped[2:].strip())}</blockquote>")
        elif (list_match := re.match(r"^(\s*)-\s+(.*)$", line)):
            if not in_list:
                out.append("<ul>")
                in_list = True
            level = min(len(list_match.group(1).replace("\t", "  ")) // 2, 3)
            class_attr = f' class="li-level-{level}"' if level else ""
            out.append(f"<li{class_attr}>{inline_md(list_match.group(2).strip())}</li>")
        else:
            close_list()
            out.append(f"<p>{inline_md(stripped)}</p>")
    close_list()
    close_table()
    return "\n".join(out)


def inline_md(text: str) -> str:
    preserved: list[str] = []

    def preserve_span(match: re.Match[str]) -> str:
        preserved.append(match.group(0))
        return f"@@RAW_SPAN_{len(preserved) - 1}@@"

    text = re.sub(r'<span class="skill-name"[^>]*>.*?</span>', preserve_span, text)
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    for index, raw in enumerate(preserved):
        escaped = escaped.replace(f"@@RAW_SPAN_{index}@@", raw)
    return escaped


def main() -> int:
    args = parse_args()
    now = utc_now()
    cutoff = now - dt.timedelta(days=args.since_days)
    root_preflight = build_root_preflight(args.project_root, cutoff)
    if args.suggest_roots_only:
        print(json.dumps(root_preflight, ensure_ascii=False, indent=2))
        return 0

    output_dir = safe_resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    roster = build_roster(args)
    tool_roots = discover_tool_roots(args.tool_root)
    git_repos = collect_git(args.project_root, cutoff, args.max_commits)
    project_files = collect_project_files(args.project_root, cutoff, limit=args.max_project_files)
    tool_results = collect_tools(tool_roots, cutoff, args.max_sessions)

    evidence = {
        "generated_at": now.isoformat(),
        "window": {"start": cutoff.isoformat(), "end": now.isoformat(), "since_days": args.since_days},
        "team": roster,
        "inputs": {
            "project_roots": [str(safe_resolve(p)) for p in args.project_root],
            "tool_roots": [str(p) for p in tool_roots],
        },
        "git_repositories": git_repos,
        "project_files": project_files,
        "tool_roots": tool_results,
        "root_preflight": root_preflight,
        "privacy": {
            "mode": "default-sensitive-exclusions",
            "note": "Skipped sensitive names, dependency/cache folders, Git internals, auth/token/secret paths, and V1-excluded collaboration systems.",
        },
    }

    summary = summarize(evidence, roster)
    markdown = render_markdown(summary, roster, cutoff, now)
    title = f"{roster['team']} AI 周进度汇报"
    (output_dir / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = output_dir / "weekly-ai-report.md"
    html_path = output_dir / "weekly-ai-report.html"
    pdf_path = output_dir / "weekly-ai-report.pdf"
    supplement_path = output_dir / "leader-supplement-guide.md"
    md_path.write_text(markdown, encoding="utf-8")
    supplement_path.write_text(render_supplement_guide(roster, summary, md_path), encoding="utf-8")
    used_huashu = try_render_with_huashu(md_path, html_path)
    if not used_huashu:
        html_doc = render_html(markdown, title)
        html_path.write_text(html_doc, encoding="utf-8")
    pdf_status = try_render_pdf_from_html(html_path, pdf_path)

    print(f"Wrote {output_dir / 'evidence.json'}")
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        print(f"Wrote {pdf_path}")
    else:
        print(f"Skipped PDF render: {pdf_status}")
    print(f"Wrote {supplement_path}")
    if used_huashu:
        print("Rendered HTML with huashu-md-html.")
    else:
        print("Rendered HTML with bundled fallback renderer.")
    return 0


def try_render_with_huashu(md_path: Path, html_path: Path) -> bool:
    skill_dir = os.environ.get("HUASHU_MD_HTML_SKILL_DIR", "").strip()
    if not skill_dir:
        return False
    renderer = Path(skill_dir).expanduser().resolve() / "scripts" / "md_to_html.py"
    if not renderer.exists() or not shutil.which("python3"):
        return False
    proc = run(["python3", str(renderer), str(md_path), "--theme", "report", "-o", str(html_path)])
    return proc.returncode == 0 and html_path.exists() and html_path.stat().st_size > 0


def try_render_pdf_from_html(html_path: Path, pdf_path: Path) -> str:
    if not html_path.exists():
        return "HTML file does not exist"
    html_uri = html_path.resolve().as_uri()
    chrome_candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    failure_notes: list[str] = []
    for chrome in chrome_candidates:
        if not chrome.exists():
            continue
        with tempfile.TemporaryDirectory(prefix="ai-weekly-report-chrome-") as profile_dir:
            proc = run(
                [
                    str(chrome),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--user-data-dir={profile_dir}",
                    f"--print-to-pdf={pdf_path}",
                    html_uri,
                ],
                timeout=30,
            )
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return "rendered with Chrome headless"
        failure_notes.append(f"{chrome.name} exited {proc.returncode}")
        if pdf_path.exists() and pdf_path.stat().st_size == 0:
            pdf_path.unlink()

    wkhtmltopdf = shutil.which("wkhtmltopdf")
    if wkhtmltopdf:
        proc = run([wkhtmltopdf, html_uri, str(pdf_path)])
        if proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            return "rendered with wkhtmltopdf"
        failure_notes.append(f"wkhtmltopdf exited {proc.returncode}")
    if failure_notes:
        return "; ".join(failure_notes)
    return "no available Chrome headless or wkhtmltopdf renderer"


if __name__ == "__main__":
    raise SystemExit(main())
