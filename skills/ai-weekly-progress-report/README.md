# AI Weekly Progress Report

Generate manager-facing weekly AI progress reports and cross-period AI learning/business practice growth reports from local AI-tool evidence, project Git activity, generated files, skill assets, and required team-leader supplements.

Local installed skills are collected as evidence assets only. They are written to `evidence.json` for review, but the default weekly report does not list external installed skills as achievements.

The package also guards against self-reference leakage. If a user scans an installed or extracted `ai-weekly-progress-report` package, its docs, scripts, templates, tests, fixtures, changelog, and regression prompts are excluded from report evidence. These files are QA/distribution assets, not the user's weekly work.

Generated project candidates are conservative and generic by default. The collector no longer carries author-specific project templates; it groups the reporter's own files and commits into neutral categories such as data/reporting, local custom skills, scripts/automation, and document/knowledge outputs. Project stages are derived from evidence strength unless the leader confirms a more specific status.

Prior generated reports are not scanned as progress evidence. Files such as `weekly-ai-report*`, `leader-supplement-guide*`, `evidence.json`, and `ai-growth-business-practice-report*` are treated as report outputs rather than current-week work. Project-local custom `SKILL.md` files and data/report artifacts such as CSV, Excel, notebook, dashboard, and report files are surfaced as conservative candidates for leader confirmation.

Weekly reports use a management structure: `本周 AI 化总体进展评估`, `一、本周进度与产出`, `二、项目层级推进`, and `三、下周计划与需协调事项`. The opening assessment is a short management-facing judgment, not a scan-count summary. Cross-period cognition and capability narratives belong to Growth Report Mode, not the default weekly report. The final report does not include a default evidence appendix; traceability stays in `evidence.json` and `leader-supplement-guide.md`.

In `一、本周进度与产出`, synthesized workflow-level items should combine task identification with `能力`、`来源`、`迁移` and `产出/归因` so managers can see both what happened this week and what reusable capability it created.

In `二、项目层级推进`, project-level items should group cross-skill, cross-file, cross-session, and cross-deliverable work into complex projects with `项目描述` and `业务价值`. Detailed action traces, paths, confidence, and evidence labels belong in `evidence.json` or the supplement guide rather than the final body.

During the interactive confirmation flow, the agent should show the generated opening assessment, progress/output draft, and project-level candidate draft directly in fenced `text` blocks, in addition to the preview Markdown path. File links alone are not enough for review.

Before confirming the body, the collector also runs a safe top-level root preflight. This catches common cases where a leader provides only one local workspace but recent AI work lives under another top-level folder. It never scans the whole home directory.

## Install

Copy this folder into the target tool's global skills directory:

- Codex macOS: `~/.codex/skills/ai-weekly-progress-report`
- Codex Windows: the configured Codex global skills directory
- QClaw/OpenClaw-style setups: the configured global skills directory
- TRAE/Claude-style tools: the configured global Skills directory for that tool

Keep the folder structure intact.

Do not install this skill only inside one project workspace. This skill is intended to scan multiple project roots and local AI tool assets, so the package should live in the tool's reusable global Skills directory on every platform.

## Quick Start

### Weekly progress report

For best HTML output, point the collector to `huashu-md-html`. The collector will render with the `report` theme, which is the recommended style for leadership weekly reports:

```bash
export HUASHU_MD_HTML_SKILL_DIR="$HOME/.codex/skills/huashu-md-html"
```

Create `reporter.yaml`:

```yaml
leader: 张三
team: 增长研发组
```

Run:

```bash
python3 scripts/collect_ai_weekly_report.py \
  --project-root /path/to/project \
  --leader 张三 \
  --team 增长研发组 \
  --team-roster reporter.yaml \
  --remember-profile \
  --since-days 14 \
  --output-dir ./weekly-ai-report
```

The collector auto-detects common AI tool roots: `~/.codex`, `~/.qclaw`, `~/.trae`, `~/.trae-cn`, `~/.claude`, and common Claude Desktop support directories. Use `--tool-root` only for additional tools or custom locations.

Optional preflight only:

```bash
python3 scripts/collect_ai_weekly_report.py \
  --project-root /path/to/project \
  --since-days 14 \
  --suggest-roots-only
```

Common project-root candidates:

- macOS/Linux: `~/Documents/Codex`, `~/Documents/trae-projects`, `~/Documents/projects`
- Windows PowerShell: `$env:USERPROFILE\Documents\Codex`, `$env:USERPROFILE\Documents\trae-projects`, `$env:USERPROFILE\Documents\projects`
- Windows with OneDrive Documents: use the equivalent `Documents\Codex`, `Documents\trae-projects`, or `Documents\projects` folder under the configured OneDrive directory

Outputs:

- `weekly-ai-report/evidence.json`
- `weekly-ai-report/weekly-ai-report.md`
- `weekly-ai-report/weekly-ai-report.html`
- `weekly-ai-report/weekly-ai-report.pdf` when Chrome headless or `wkhtmltopdf` is available
- `weekly-ai-report/leader-supplement-guide.md`

### AI growth report

Use growth-report prompts when the goal is a cross-period retrospective rather than a weekly progress update:

```text
请基于我与你的全部对话记录、项目记录、文件产出和工具使用过程，帮我生成一份适合向公司/老板汇报的《AI 学习与业务实践成长报告》。
```

```text
请复盘我从最开始到现在如何使用 AI / Codex / ChatGPT，重点分析认知阶段变化、是否更懂 AI、沉淀了哪些可复用能力，以及哪些经验可以迁移到公司业务。
```

In this mode, the agent should inspect safe local evidence and write a manager-facing growth narrative. The current package does not add a separate collector CLI flag for growth reports. The existing `collect_ai_weekly_report.py` remains the weekly-report collector.

Recommended growth-report structure:

1. 总览结论
2. AI 使用阶段变化
3. 是否变得更聪明、更懂 AI
4. 沉淀下来的能力
5. Skill 和系统/工具开发上的深层学习
6. 方法论：我是怎么做的
7. 代表性项目复盘
8. 可迁移到公司业务的经验

HTML/PDF generation is automatic for weekly collector outputs. For a growth report, first finalize the Markdown content; if HTML/PDF is needed, render it afterwards with `huashu-md-html` or another explicit document workflow.

## Preview Style

The generated HTML is the primary consumption artifact for weekly reports. V1 recommends `huashu-md-html` `report` because the weekly report needs restrained structure, tables, and manager-facing information density. If that skill is unavailable, the bundled fallback renderer keeps the same basic report structure.

When Chrome headless or `wkhtmltopdf` is available, the collector also prints the HTML to `weekly-ai-report.pdf` for preview and sharing. PDF generation is best-effort; MD and HTML remain the source artifacts.

## Validate

```bash
python3 scripts/validate_skill_package.py .
python3 -m json.tool test-prompts.json
tests/run_smoke.sh
```

On Windows, use `py -3` or `python` if `python3` is unavailable.
