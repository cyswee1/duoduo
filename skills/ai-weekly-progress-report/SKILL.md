---
name: ai-weekly-progress-report
description: Generate evidence-based weekly AI work progress reports and cross-period AI learning/business practice growth reports for team leaders from local AI-tool assets, Git repositories, generated files, and required human supplements. Use when preparing AI transformation weekly reports, AI progress meetings, team AI adoption updates, skill/methodology progress summaries, AI learning growth reports, business practice growth reports, stage retrospectives, self-growth summaries, boss-facing AI practice reports, or manager-facing AI work reports.
---

# AI Weekly Progress Report

Use this skill to help a team leader prepare either a concise weekly AI progress report or a cross-period AI learning and business practice growth report for senior management. The report is not a performance score. It turns local evidence plus leader-confirmed supplements into a standardized management-facing narrative.

## Run Modes

Choose the mode before scanning or writing:

- `Weekly Progress Mode`: use when the user asks for this week, weekly progress, AI weekly report, weekly meeting, next-week plan, team member AI progress, or a standard progress update. Follow the collector workflow, then add a management synthesis pass before asking for confirmation. Produce a concise management weekly report: short overall AI progress assessment with capability/cognition signals, current progress/output, project-level movement, and human-owned next-week plan. Keep evidence in `evidence.json` and the supplement guide rather than the final report body.
- `Growth Report Mode`: use when the user asks for "from the beginning until now", AI learning growth report, business practice growth report, stage retrospective, self-growth summary, boss-facing AI practice report, cognitive changes, whether they became smarter or understand AI better, reusable capabilities, skill/tool/system learning, how they did the work, or how experience transfers to company business.

If a request contains both weekly progress and long-period growth language, ask once which report should be primary. If the user provides a fixed structure for the growth report, preserve that structure unless it conflicts with evidence or safety rules.

## Run Context

Before scanning, identify:

- Report mode: `Weekly Progress Mode` or `Growth Report Mode`.
- Reporting window: default to the 14 days before generation unless the user specifies another window.
- Reporter profile: if leader/team are not known, ask once and save them with `--remember-profile`.
- Install context: this package should be installed in the AI tool's reusable global Skills directory, not only inside one project workspace.
- Platform roots: auto-detect `~/.codex`, `~/.qclaw`, `~/.trae`, `~/.trae-cn`, `~/.claude`, and common Claude Desktop support directories; use `--tool-root` for other non-default tools.
- Project roots: use explicit `--project-root` values for Git/project scanning. Before generating, run or explain the safe top-level root preflight. Do not run broad home-directory discovery.
- Distribution target: macOS/Linux use `python3`; Windows users may use `py -3` or `python`.

For `Growth Report Mode`, the reporting window may span the full available local evidence history. Still respect the privacy exclusions and never perform broad home-directory discovery unless the user explicitly provides roots.

## Required Inputs

Collect these before finalizing a report:

1. Leader/team YAML with leader and team name. Team member collection is not part of the default report flow.
2. One or more project roots, if there are Git/project directories to scan.
3. Optional tool roots for AI tools not auto-detected.
4. Leader supplements for every required module, or explicit confirmation that there is no supplement.

The `members` list is optional and ignored by the default report template. Do not ask for team members unless the user explicitly requests a people-by-people appendix.

## Installation Rule

- Install this skill in the target tool's global Skills directory on every platform.
- Do not treat a project repository copy as the runnable install location.
- The project repository may keep the source package for maintenance, testing, and bundling, but the active runtime copy should live under the tool-level Skills directory such as `~/.codex/skills/`, the TRAE global Skills directory, or the equivalent Windows global skills path.

Minimal roster:

```yaml
leader: 张三
team: 增长研发组
members:
  - name: 李四
    role: 前端
  - name: 王五
    role: 后端
```

Minimal roster without members:

```yaml
leader: 张三
team: 增长研发组
```

## Trigger Prompt

Use this fixed trigger pattern when the user wants the standard flow:

```text
使用 ai-weekly-progress-report，按正式流程生成本周 AI 周进度汇报。
```

If the user says `调用 ai-weekly-progress-report 技能，按正式流程跑` or equivalent, treat it as this trigger and start from the evidence draft.

Use `Growth Report Mode` for prompts like:

```text
请基于我与你的全部对话记录、项目记录、文件产出和工具使用过程，生成 AI 学习与业务实践成长报告。
```

```text
帮我写一份适合给老板看的 AI 阶段复盘，重点说明我如何使用 AI、认知如何变化、沉淀了什么能力，以及这些经验如何迁移到公司业务。
```

## Workflow

Use the mode selected in `Run Modes`.

## Weekly Progress Workflow

1. Read `references/privacy-exclusions.md` before scanning.
2. Run the collector to create the source draft and pure Markdown supplement guide:

```bash
python3 "<skill-dir>/scripts/collect_ai_weekly_report.py" \
  --project-root "<repo-or-project-root>" \
  --leader "<reporter-name>" \
  --team "<team-name>" \
  --team-roster "<members.yaml>" \
  --remember-profile \
  --since-days 14 \
  --max-project-files 3000 \
  --output-dir "./weekly-ai-report"
```

3. Review the root preflight before trusting the draft. The collector checks only safe top-level candidates, not the whole home directory. Common candidates are:
   - macOS/Linux: `~/Documents/Codex`, `~/Documents/trae-projects`, `~/Documents/projects`
   - Windows: `%USERPROFILE%\Documents\Codex`, `%USERPROFILE%\Documents\trae-projects`, `%USERPROFILE%\Documents\projects`, plus common OneDrive Documents equivalents
   If `leader-supplement-guide.md` suggests missing roots, rerun with those paths as additional `--project-root` values before asking the leader to confirm the content.
4. Treat the first collector output as a source draft, not the final meeting artifact. The reference document must be pure Markdown (`leader-supplement-guide.md`) so the leader can read and paste from it without HTML noise.
5. Create a `Management Synthesis Layer` before presenting the body for confirmation. This is an agent writing step over `evidence.json`, `weekly-ai-report.md`, and `leader-supplement-guide.md`; do not simply paste the collector's raw bullets as the report body.
   - Convert raw file paths, skill names, session hints, and directory names into 2-4 management-readable themes.
   - Preserve concrete local project names when evidence or leader supplements identify them, for example a named business analysis project, a named content workflow project, or a named internal automation project; never use generic parent directory names such as `projects`, `project`, date folders, or `new-chat` as project titles in the final body.
   - Keep weak evidence out of the final body unless it is clearly phrased as a conservative scan result. Do not promote file-name matches, installed skills, or session titles into completed achievements without project evidence or leader confirmation.
   - Use the `Conversation Evidence Layer` to connect session titles, archived sessions, and project files. Session text may provide project/file path hints and work-theme signals, but it remains weak evidence unless it cross-references concrete local artifacts or the leader confirms it.
   - Weekly cognition must not disappear. Summarize current-week capability, judgment, communication, or work-mode change in `本周 AI 化总体进展评估` and, when relevant, attach it to concrete progress bullets as value context. Do not create an independent weekly `认知和方法论沉淀` module.
   - The synthesized body should lead with management value. Raw paths belong in `evidence.json` or the supplement guide, not as the headline content.
6. Ask only for the required human confirmations first, in this order:
   - `第零步：扫描范围预检`: show the scanned roots, suggested roots, and possible missing project signals. If suggested roots exist, recommend rerunning with the top-level directories before confirming the body.
   - `一、本周进度与产出`: first show the preview Markdown path, then show the synthesized management draft directly in the conversation inside one fenced `text` block. The text block must include `本周 AI 化总体进展评估` and `一、本周进度与产出` so the leader can judge the wording without opening the file. Treat the scanned table as locked source text: do not ask the leader to rewrite it. Ask only for `自主说明` under this section, using this guide text: `请检查内容，必要信息输入说明（如未能识别或总结不准确的内容；团队成员工作产出等）`.
   - `二、项目层级推进`: show synthesized project-level candidates in a fenced `text` block. Treat the scanned table as locked source text: do not ask the leader to rewrite, delete, or merge it during the default flow. Ask only for `自主说明` under this section, using the same guide text. This section groups cross-skill, cross-file, cross-session, and cross-deliverable work into complex projects. The body must be a business-level management summary, not an audit trail: each item should include only `项目描述` and `业务价值`. Put detailed action traces, confidence, file paths, session hints, and evidence labels in `evidence.json` or the supplement guide. Do not show raw directory buckets as project names.
   - `三、下周计划与需协调事项`: ask only for two leader-friendly fields: `下周计划` and `风险与待支持`. Do not auto-generate next-week plans, priorities, owners, or coordination asks unless the leader explicitly provides them; use `待主管补充` or an empty placeholder in source drafts.
7. When the leader mentions cognition changes, communication judgment, team arrangements, or business judgment, fold them into the relevant progress/output bullet as value context. Do not present cognition as an independent default weekly-report section, but do preserve it as a management signal in the opening assessment and concrete outputs.
8. The weekly opening section is `本周 AI 化总体进展评估`: write 2-3 concise management-facing assessment bullets. Start with current-week work-mode, capability, or judgment change, then point to supporting evidence. Do not make scan counts the main conclusion, and do not expand it into a long-period growth narrative.
9. Only after autonomous notes and next steps are confirmed, rewrite the report into a clean preview draft. The final preview must not contain `[需主管确认]`, `[需主管补充]`, "请主管确认", per-bullet confirmation instructions, raw candidate dumps, raw directory bucket names as project titles, evidence appendices, or AI-invented next-week plans.
10. Generate Markdown and HTML from the clean final Markdown. Also generate `weekly-ai-report.pdf` by printing the HTML when a local HTML-to-PDF engine is available. Prefer Chrome headless on macOS, then `wkhtmltopdf` when installed. If PDF generation fails, report the failure explicitly and keep MD/HTML as the preview source.
11. Present the preview package paths and ask the leader to confirm whether the preview draft should be accepted or revised.

## Growth Report Workflow

Use this workflow for cross-period AI learning and business practice growth reports:

1. Read `references/privacy-exclusions.md` and `references/report-rubric.md` before gathering evidence.
2. Inspect only user-provided roots and safe local AI-tool assets. Prefer project files, generated reports, skill packages, test prompts, scripts, dashboards, HTML/PDF/Excel outputs, and local AI session indexes. Treat session titles as hints, not proof.
3. Build an evidence map with four layers:
   - concrete artifacts: local files, scripts, reports, dashboards, generated HTML/PDF/Excel, deployment assets, state files
   - reusable assets: `SKILL.md`, `test-prompts.json`, references, validators, package files, knowledge registries
   - tool/process traces: session titles, tool roots, run summaries, command outputs, generated evidence files
   - human supplements: explicit user-provided explanations, priorities, business context, and missing owner confirmations
4. Write the report around cognitive and capability change before listing projects. A growth report must answer how the user used AI, what changed in their judgment, whether they became more capable with AI, what reusable abilities emerged, how skill/tool/system development matured, how they worked, and what can transfer to company business.
5. Use this default structure unless the user supplied another structure:
   - `一、总览结论`
   - `二、我的 AI 使用阶段变化`
   - `三、我是否变得更聪明、更懂 AI`
   - `四、我沉淀下来的能力`
   - `五、我在 skill 和系统/工具开发上的深层学习`
   - `六、我是怎么做的`
   - `七、代表性项目复盘`
   - `八、可迁移到公司业务、团队协作或未来项目中的经验`
6. In each section, connect claims to representative evidence. Do not over-cite file paths in the main prose; group evidence naturally and keep the report readable for a non-technical manager.
7. If evidence is weak, say so. Use phrases such as `从本地证据可以判断`, `主要来自会话标题线索`, `需要人工确认`, or `这部分更像可迁移经验而非已验证成果`.
8. Growth reports do not use the collector's weekly MD/HTML/PDF package by default. If the user wants HTML/PDF, render the final Markdown with `huashu-md-html` or another explicit document workflow after the content is accepted.

## Data Flow

`profile + leader/team + project roots + tool roots` → safe top-level root preflight → `scripts/collect_ai_weekly_report.py` → `evidence.json` + source draft + pure-MD `leader-supplement-guide.md` → management synthesis layer → confirmation for root coverage, section-level autonomous notes, and next steps → clean preview MD/HTML/PDF.

The script creates a source draft, not a final management judgment. The agent must show the root preflight, preview path, and fenced `text` previews of the synthesized opening assessment, progress/output draft, and project-level candidates in the conversation. For `一、本周进度与产出` and `二、项目层级推进`, the scanned text is locked by default; ask only for section-level `自主说明`. Do not show only file links and response options.

## Report Rules

- Do not score individuals or imply performance ranking.
- Do not include a default team-member progress module. If the user explicitly requests a people appendix, do not infer team-member progress from another person unless the leader confirms it.
- For growth reports, do not write motivational fluff, a project-only list, or a generic "AI changed everything" narrative. The report must be evidence-linked and behavior-specific.
- For growth reports, do not claim the user authored or built a skill merely because it is installed locally. Separate self-developed/iterated assets, externally installed/synced assets, and uncertain ownership.
- For growth reports, session titles and tool usage traces are weak evidence. Use them to guide investigation and phrase conclusions conservatively unless supported by files, outputs, or user confirmation.
- For growth reports, explain skill names as capability themes such as knowledge-base building, skill governance, content/document production, growth diagnostics, operations automation, or team enablement.
- Label weak evidence lightly: `证据充分`, `需人工确认`, or `主要来自人工补充`.
- Prefer concrete artifacts: commits, changed docs, skill files, local AI session titles, generated report files, demos, scripts, and project folders.
- Keep DORA-style delivery signals as context only; do not use them as productivity or绩效 metrics.
- The main report is for non-technical management. First express the value judgment in business/management language, then put tool names and file paths in short attribution notes.
- Do not list raw skill names as achievements unless the value is clear. Group them into capability themes such as knowledge-base building, skill governance, content production, growth diagnostics, or operations automation.
- When evidence implies a higher-level workflow, synthesize it as an initiative in plain text instead of leaving scattered technical details in the body.
- Weekly reports must include current-week capability/cognition signals, but only as management assessment or value context attached to evidence-backed work. The balance is: cognition is preserved, independent cognition modules are not.
- The management synthesis layer must turn raw candidates into business-readable themes before user confirmation. The user should not have to review a raw evidence dump as the main weekly report.
- `三、下周计划与需协调事项` is human-owned input. The agent may ask for it, format it, and preserve confirmed wording, but must not invent next-week plans or support needs from scanned evidence.
- Project file collection must preserve coverage across multiple workspace areas. If one project has hundreds of matching files, sample or rank it so later projects are still represented; do not use first-come path order as the effective coverage policy.
- `--max-project-files` is a performance/noise control, not a business coverage definition. Default to a high enough value for active workspaces, and increase it for employees with many generated artifacts. If the selected evidence appears capped or skewed, rerun with a larger value or with more specific `--project-root` values.
- Conversation evidence should be used for recall and project grouping, not as proof by itself. Read session indexes and archived session metadata/text only to extract titles, project/file path mentions, and matched work themes; do not store or report raw chat content.
- Never use this skill package's own files as evidence for a user's weekly progress. `ai-weekly-progress-report` package docs, scripts, templates, tests, fixtures, `test-prompts.json`, changelog, and release files are QA/distribution assets, not user work. If a coworker scans an extracted package or installed skill directory, those files must not generate progress bullets or project candidates.
- Never use generated weekly-report or growth-report artifacts as default progress evidence. Prior `weekly-ai-report*`, `leader-supplement-guide*`, `evidence.json`, or `ai-growth-business-practice-report*` files are outputs of reporting workflows; they can easily contain another person's summary and must not be re-read as the current reporter's achievements.
- Synthesized progress and project-level candidates require strong evidence from explicit project files or Git commits. Session titles and installed skills are weak hints for investigation and leader confirmation; they must not by themselves create default achievements.
- Default synthesis must use generic evidence categories rather than embedded author project templates. Generic `质量`、`回归`、`汇报` or `周报` wording can surface as weak local work signals, but must not become a named productization or skill-governance achievement unless the reporter's own project files, commits, or supplement proves it.
- Project-level body text must not render long `本周推进动作`, `关键证据`, or `当前阶段` audit fields by default. If those details are useful, keep them in `evidence.json` or `leader-supplement-guide.md`, not in the final report body. Pattern copy may classify the project goal, but must not claim a specific trial, release, production status, account cadence, or deployment unless the evidence or leader supplement confirms it.
- The default body should be management-readable and capped: `本周进度与产出` should usually contain 2-6 synthesized themes, and `二、项目层级推进` should contain no more than 6 project movements.正文不得直接罗列路径清单；路径、逐条证据和弱线索只进入 `evidence.json` or the supplement guide.
- Body copy must use business-level descriptions, not evidence-status wording. Avoid `线索`, `候选`, `证据充分`, `需主管确认`, `文件数量`, `当前判断`, `管理判断`, and `归因线索` in the final body; those belong in the supplement flow or evidence file.
- `一、本周进度与产出` should render as a management table with `进展主线`, `项目描述`, and `业务价值`, followed by `### 自主说明`. Do not include a produced-skills column by default; skill attribution is too easy to misclassify from local evidence and belongs in `evidence.json` or a manually confirmed supplement.
- `二、项目层级推进` should also render as a management table with `项目主线`, `项目描述`, and `业务价值`, rather than nested bullets.
- Project-level titles must be meaningful business or local project names. Do not output parent folder buckets such as `projects`, `project`, date folders, `new-chat`, or tool cache names as project names; use them only as evidence paths in `evidence.json` or as weak follow-up hints.
- In `本周进度与产出`, do not output a default external installed/synced skill list. Installed skill directories are evidence assets only; they may appear in `evidence.json` and the supplement guide, but not as default report achievements.
- Do not let package QA prompts, author examples, prior generated reports, or old install artifacts become business content. Domain-specific labels such as 投放、SEO、知识库、蒸馏、XMP、内容生产, or data analysis may enter the final body only when supported by current reporter project files, commits, or explicit leader supplements. Otherwise keep them as weak evidence or omit them from the visible report.
- If a user passes an AI tool root such as `~/.qclaw`, `~/.codex`, `~/.trae`, or `~/.trae-cn` as a project root, scan workspace/project artifacts conservatively but exclude its global `skills/` library from project evidence. Installed skill descriptions are capability context, not the reporter's deliverables.
- Tool-root internal state such as sessions, memories, backups, plugin caches, logs, devices, sync state, and config JSON is not project evidence. These files may help the tool operate, but they can contain stale or third-party themes and must not generate report body content.
- Project-local `SKILL.md` files under explicit project roots are different from globally installed external skills. Surface them as conservative `项目本地自定义 Skill / 工作流资产` candidates, and require the leader to confirm whether they were newly created or iterated this week.
- Data-analysis and report artifacts such as CSV, Excel, notebook, dashboard, or report files should be surfaced as `数据分析 / 报表产物线索` when modified in the reporting window. Do not require AI keywords for these files; ask the leader to confirm the analysis object, conclusion, and business use.
- If a concrete project identity appears in the reporter's own files, paths, commits, sessions, or leader supplements, preserve that local project name in the candidate. Do not inject example project names from this package into another user's report.
- Weekly reports explain progress. Growth reports explain cognition. Do not output `认知和方法论沉淀` as an independent default weekly-report section.
- The default weekly report has `本周 AI 化总体进展评估` plus three main modules: `一、本周进度与产出`, `二、项目层级推进`, and `三、下周计划与需协调事项`. Do not include a default evidence appendix in the final report; keep traceability in `evidence.json` and the supplement guide.
- Treat HTML as the primary consumption artifact. Keep the Markdown clean enough to render through `huashu-md-html`; use report-friendly tables, restrained bold headlines, and a small KPI/status block rather than decorative cards.
- When a confirmed progress/output bullet cites a skill name, mark it with `skill-name` HTML styling and explain the capability in Simplified Chinese before showing tool attribution.
- Do not render workflow diagrams or flow strips in V1. Multi-skill workflows should be explained in plain text for consistency across teams.

## Safety

- Never read `.env`, auth files, tokens, keys, caches, dependencies, or large binary files.
- Do not scan chat, Feishu, DingTalk, Notion, Jira, TAPD, or email in V1.
- Treat local AI session titles as hints, not proof.
- If evidence is sparse, ask for human confirmation instead of inventing progress.

## Validation

Minimum checks before sharing:

```bash
python3 scripts/validate_skill_package.py .
python3 -m json.tool test-prompts.json
tests/run_smoke.sh
```

If the local machine supports HTML-to-PDF conversion, confirm the collector writes `weekly-ai-report.pdf`; otherwise confirm it reports that PDF rendering was skipped.

Windows equivalents:

```powershell
py -3 scripts/validate_skill_package.py .
py -3 -m json.tool test-prompts.json
```

Before publishing a GitHub bundle, run:

```bash
python3 scripts/build_bundle.py . dist/ai-weekly-progress-report.zip
```

## References

- Report module definitions and confidence rules: `references/report-rubric.md`
- Privacy exclusions: `references/privacy-exclusions.md`
- Cross-platform distribution: `references/portability-guide.md`
- Release checklist: `references/release-checklist.md`
