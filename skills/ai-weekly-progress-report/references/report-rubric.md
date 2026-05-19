# AI Weekly Report Rubric

## Weekly Progress Rubric

Use this rubric for `Weekly Progress Mode`.

## Default Weekly Structure

### 第零步：扫描范围预检

Before asking the leader to confirm the body, show which project roots were scanned and whether safe top-level candidates may have been missed. This is an interaction checkpoint, not a main report module. If suggested roots exist, recommend rerunning with the top-level directories first.

Use platform-aware candidates only:

- macOS/Linux: `~/Documents/Codex`, `~/Documents/trae-projects`, `~/Documents/projects`
- Windows: `%USERPROFILE%\Documents\Codex`, `%USERPROFILE%\Documents\trae-projects`, `%USERPROFILE%\Documents\projects`, plus common OneDrive Documents equivalents

Do not scan the whole home directory.

### 本周 AI 化总体进展评估

Use 2-3 concise management-facing bullets to assess the current week's AI progress. Start with work-mode or capability change, then connect it to supporting evidence. Do not turn evidence counts into the main conclusion, and do not expand this section into a cross-period growth narrative. If evidence is weak, say that the scan is insufficient and needs leader confirmation.

This section must preserve current-week cognition and capability movement in a restrained way. Acceptable content includes a change in work mode, judgment quality, reusable capability, collaboration pattern, validation habit, or business framing. Do not create a separate cognition module in the weekly report; fold the signal into the opening assessment and the relevant output bullets.

### 一、本周进度与产出

Capture concrete current-week progress, outputs, and reusable assets. This section may include:

- business/project outputs
- AI-assisted scripts, tests, reports, demos, docs, dashboards, HTML/PDF, or other deliverables
- self-developed or iterated skills, rules, prompts, templates, MCP/tooling conventions, checklists, and repeatable workflows
- method or cognition changes only when attached to a concrete output or leader supplement

Installed skills prove local availability, not authorship, use, or business delivery. If a scanned skill was truly developed, optimized, or used during the reporting window, require project evidence, session evidence, file evidence, or leader confirmation before including it in `本周进度与产出`.

Project-local `SKILL.md` files under explicit project roots should be shown as conservative custom-skill/workflow candidates. This is intentionally different from globally installed external skills, which remain evidence assets only.

Data-analysis and report artifacts are legitimate weekly progress signals even when they do not contain AI keywords. CSV, Excel, notebook, dashboard, or report files should be surfaced as data/report candidates with conservative wording and a request for leader confirmation of analysis object, conclusion, and business use.

Generated report artifacts must not be used as progress evidence. Prior `weekly-ai-report*`, `leader-supplement-guide*`, `evidence.json`, and `ai-growth-business-practice-report*` outputs often contain synthesized text or another person's examples, and re-reading them creates cross-user leakage.

Weekly reports should not output an independent `认知和方法论沉淀` module. If cognition, communication judgment, team arrangements, or business judgment matter, fold them into the relevant progress bullet as value context.

Do not collapse clearly identifiable local projects into generic labels when evidence exists. Preserve names that appear in the reporter's own paths, files, commits, sessions, reports, prompts, or leader confirmation. Do not inject example project names from this package into another user's report.

Before presenting this module, run a management synthesis pass over raw candidates:

- Group raw file paths, local skills, session hints, and report files into 2-4 business-readable themes.
- Lead each bullet with the management value or business process change, not the tool name or path.
- Use raw paths only in `evidence.json` or the supplement guide; do not move long evidence details into the final report body.
- If the collector has only weak signals, phrase the item as a candidate and ask for leader confirmation instead of outputting a long raw list.
- Preserve cognition as value context when it explains why the output matters, such as "从一次性处理转向可复用流程", "开始用证据链约束 AI 输出", or "把业务判断前置到采集和验证规则中".

For synthesized workflow-level progress, prefer a compact four-field bullet:

- headline: task identification and manager-facing description
- `能力`: what reusable capability changed or emerged
- `来源`: which evidence family supports the judgment
- `迁移`: where the capability can transfer in company business
- `产出/归因`: skill names, deliverables, files, scripts, reports, or other attribution signals

This structure should combine the readability of a progress report with the capability/source/transfer clarity of a growth report. Keep it concise; do not let the weekly report become a long growth-report chapter.

### 二、项目层级推进

Group complex work into project-level movements when multiple signals point to the same business or operating-system project. This section should not repeat individual skill bullets from `一、本周进度与产出`.

Project titles must be meaningful local project or business initiative names. Use names from paths, files, prompts, sessions, reports, commits, or leader confirmation when they exist, such as a named data-analysis project, a named content workflow, a named internal automation, or a human-supplied project name. Do not use parent folder buckets such as `projects`, `project`, date folders, `new-chat`, `output`, or tool cache names as the displayed project title. If only a bucket name exists, keep the item as a weak follow-up candidate or merge it into a broader neutral theme.

Each body item must include:

- `项目描述`: what this project direction is doing at the business or management level
- `业务价值`: the larger business or operating-system problem being solved

Detailed `本周推进动作`, `关键证据`, `当前判断`, `可信度`, file paths, session hints, and raw evidence labels belong in `evidence.json` or the supplement guide, not in the final body.

### 一、本周进度与产出

Render this module as a management table with three columns:

- `进展主线`: the synthesized workstream
- `项目描述`: business-level description of what the workstream does
- `业务价值`: why management should care

Do not include a produced-skills column by default. Local evidence can easily confuse installed skills, project-local skills, test fixtures, and generated report packages, so skill attribution belongs in `evidence.json` or a manually confirmed supplement.

### 二、项目层级推进表格

Render this module as a management table with three columns:

- `项目主线`: the project or business initiative name
- `项目描述`: business-level description of what the project does
- `业务价值`: why management should care

Installed skills alone are not enough evidence for a project. Use project files, session evidence, commits, historical report artifacts, or explicit leader confirmation. Medium-confidence projects may appear as candidates, but the wording must not imply completed delivery.

The report package itself is not evidence. If a scanned directory contains an installed or extracted `ai-weekly-progress-report` package, exclude its docs, scripts, templates, tests, fixtures, `test-prompts.json`, changelog, and release files from progress and project synthesis. These artifacts describe the skill's own QA cases and may contain example project names; they must not leak into a coworker's weekly report.

For default generation, project-level candidates require strong local evidence from explicit project files or Git commits. Session-title-only matches may guide follow-up questions, but should not become default project bullets without leader confirmation.

Conversation evidence can improve recall when it links a session to a concrete project/file path or artifact family. Use session titles, archived sessions, and path mentions to connect related work, but keep the confidence conservative unless file evidence or leader confirmation supports the claim. Do not quote raw chat text in the report body.

Default project synthesis must be generic and evidence-led. Generic words such as `质量`, `回归`, `汇报`, `周报`, or `skill` may create conservative work signals, but they are not enough to trigger named author-specific projects, productization claims, or project-status language.

Render project-level body as a business-level management summary. Do not copy prewritten personal project status into another user's report. Use concrete wording about what business or operating problem the project addresses, such as "围绕外呼、分期、成本清洗和业务复盘流程，沉淀数据处理、异常判断和复盘交付方法." Avoid evidence-status wording such as "候选", "线索", "证据充分", or "需主管确认" in the body.

Project-level synthesis should be a management summary, not a raw evidence dump. Prefer 2-4 project movements and cap default output at 6. Merge scattered weak file matches under a neutral candidate such as `数据分析与报表流程整理` only when the evidence points to the same business process; otherwise leave them in `evidence.json` or the supplement guide.

### 三、下周计划与需协调事项

Ask the leader to design the next step, not just summarize the past. Include:

- `下周计划`: 下一步要推进的 AI 化动作、试点范围、交付物或节奏。
- `风险与待支持`: 已识别风险、阻塞、需要管理层决策/资源/权限/跨团队协作的事项。

This module is human-owned. The agent must not infer or invent next-week plans, owners, priorities, or support needs from local evidence. In source drafts, use empty placeholders or `待主管补充`. In final drafts, include only leader-confirmed next steps or explicitly state `暂无补充`.

### Evidence Traceability

Keep evidence in `evidence.json` and the supplement guide. It should support review and auditability, but it should not become a final report module by default.

## Confidence Labels

- `证据充分`: local evidence and human confirmation agree, or multiple local artifacts support the same claim.
- `需人工确认`: local evidence exists but the work meaning, owner, or management relevance is unclear.
- `主要来自人工补充`: evidence is absent or weak, but the leader explicitly supplied the content.

## Style

- Use manager-facing bullets, not audit prose.
- Keep each required module to 3-5 high-signal bullets unless the leader asks for detail.
- Use restrained structure: bold the task/capability headline, explain value, then add compact capability/source/transfer/output attribution when the item is synthesized from multiple signals.
- Put evidence and confidence in a short final section, not after every sentence.
- Treat HTML as the reader-facing version. Prefer `huashu-md-html` `report` theme with clean section bullets and restrained tables.
- Mark skill names visually with `skill-name` styling so readers can separate tool attribution from management conclusions.
- Use Simplified Chinese for explanatory text by default. English skill names are allowed only as attribution labels.
- For self-developed multi-skill workflows, explain the workflow's management value in plain text. Do not use workflow diagrams or flow strips in V1.
- Avoid performance scoring, rankings, individual capability judgments, and default people-by-people progress modules.
- Every bullet should answer `so what`: what capability changed, what management problem it reduces, or what next action it enables.
- Use technical names as attribution, not as the headline. Prefer `建立知识库问答闭环` over `knowledge-orchestrator`.
- Group raw assets into capability themes before reporting: knowledge-base pipeline, skill governance, content/document production, growth diagnostics, operations automation, or team enablement.
- If the collector only has file names or skill names, keep the final report conservative and ask the leader for value judgment in the supplement flow rather than repeating confirmation prompts in the report body.
- Weekly supplement flow must show the root preflight, preview Markdown path, and fenced `text` blocks containing the synthesized `本周 AI 化总体进展评估`, `本周进度与产出`, and `项目层级推进` drafts directly in the conversation, then ask the leader to confirm, supplement, delete, merge, or rewrite. Do not provide only file links or only the response options. Ask for next-week plan only after root coverage, current-week output, and project-level candidates are confirmed.
- Workspace coverage must be balanced. A large active project folder must not consume the project-file evidence limit before later project roots or sibling projects are considered. Prefer full candidate scan plus diversity/ranking, or rerun with more specific `--project-root` values when coverage remains suspicious.
- The project-file limit is a performance and noise-control setting, not a statement that the employee has only that many outputs. For heavy users, increase `--max-project-files` or split explicit project roots until the evidence map includes all major work areas.
- Use conversation evidence for project recall only after applying privacy boundaries: extract titles, timestamps, local path mentions, and matched work themes; do not include raw messages or personal chat content in final reports.

## Growth Report Rubric

Use this rubric for `Growth Report Mode`: AI learning growth reports, business practice growth reports, stage retrospectives, self-growth summaries, and boss-facing AI practice reports. The purpose is to explain how the user's AI usage matured over time, not to summarize one reporting week.

### Required Growth Sections

#### 1. 总览结论

Use 3-5 sentences. State the user's core growth plainly: for example, from using AI as a tool to designing AI-assisted workflows, reusable assets, evidence systems, or business automation. Do not use slogans.

#### 2. AI 使用阶段变化

Divide the history into 4-6 stages by time or cognitive progression. Each stage should include:

- 阶段名称
- 当时主要在做什么
- 对 AI 的理解发生了什么变化
- 代表性项目、文件、会话标题或工具证据

Stages should show a real progression, such as tool trial, business task automation, skillization, knowledge-base/evidence governance, engineering quality governance, and management/team transfer.

#### 3. 是否变得更聪明、更懂 AI

Answer directly. Analyze concrete changes in:

- 判断力
- 复杂问题拆解
- AI 能力边界理解
- 流程设计、验证结果、沉淀方法
- 对 AI 底层工作逻辑的理解

Avoid motivational language. Tie each claim to behavior, artifacts, or repeated project patterns.

#### 4. 沉淀下来的能力

Summarize 4-6 capability groups. For each group, include:

- 能力是什么
- 通过什么项目、对话或工具实践练出来
- 如何迁移到公司业务

Recommended capability groups: business problem decomposition, data-source and evidence governance, AI workflow design, local engineering/tool implementation, skill/prompt/knowledge asset management, automation boundary and human review judgment.

#### 5. Skill 和系统/工具开发上的深层学习

Explain whether the user moved from prompt writing to executable workflow design. Cover:

- Skill is not a prompt; it is a reusable operating procedure with triggers, inputs, workflow, resources, scripts, boundaries, and tests.
- Difference between function categories, governance categories, project localization, and reuse boundaries.
- Turning AI output into deliverables such as HTML, Excel, PDF, dashboards, scripts, APIs, state files, registries, or test prompts.
- Using tests, interfaces, fields, raw evidence, and official sources to constrain AI output.

#### 6. 我是怎么做的

Convert the user's practice into a repeatable methodology. A good sequence is:

1. 定义业务对象
2. 拆输入来源
3. 设置规则和边界
4. 让 AI 落地成文件或工具
5. 验证输出是否可用
6. 沉淀为可复用资产
7. 复盘并优化流程

#### 7. 代表性项目复盘

List representative projects or attempts. For each project, include:

- 项目名称
- 想解决的问题
- AI / Codex 在里面承担什么角色
- 关键产出
- 可迁移价值

Prefer a compact table when there are many projects. Do not let this section dominate the report; it supports the growth argument.

#### 8. 可迁移到公司业务、团队协作或未来项目中的经验

Translate personal practice into organizational value: reporting standardization, data automation, knowledge-base production, skill governance, content production, growth diagnostics, operations automation, onboarding/training, and cross-team collaboration.

### Growth Evidence Layers

Use evidence in this order:

1. **Concrete artifacts**: local files, scripts, generated reports, dashboards, HTML/PDF/Excel outputs, deployment assets, state files, package archives.
2. **Reusable assets**: `SKILL.md`, `test-prompts.json`, references, validators, templates, knowledge registries, release notes.
3. **Tool and process traces**: AI session titles, tool roots, run summaries, command outputs, generated `evidence.json`.
4. **Human supplements**: explicit user statements, business context, owner confirmation, missing rationale.

Session titles are weak evidence. Installed skills prove local availability, not authorship. When ownership, business impact, or completion status is unclear, label the claim as `需人工确认` or phrase it as a capability signal instead of a completed achievement.

### Growth Style

- Lead with cognition and capability change, then use projects as evidence, then explain company transfer value.
- Write for a company leader or boss: clear, concrete, and manager-facing.
- Avoid empty praise, generic AI slogans, and project-only chronology.
- Do not score the user, rank team members, or imply performance evaluation.
- Do not claim "became smarter" abstractly; explain smarter judgment through observed behaviors.
- Use first-person framing only when the user requests it. Otherwise, use a report voice.
- Keep technical names as attribution, not the main achievement. Prefer `建立知识库问答闭环` over `knowledge-orchestrator`.
- Separate self-developed/iterated assets, externally installed/synced assets, and uncertain ownership.
- If the final report is long, use tables for project recap and concise bullets for capabilities.
