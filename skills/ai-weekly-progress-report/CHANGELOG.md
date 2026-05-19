# Changelog

## 0.2.3

- Removed `test-prompts.json` from distributable runtime bundles so teammate installs do not carry QA prompt vocabulary into skill context.
- Replaced concrete author-project examples in runtime guidance with neutral placeholders.
- Tightened project synthesis so domain-specific themes such as 投放, SEO, 知识库, 蒸馏, or XMP require strong current-reporter evidence instead of broad keyword matches.
- Excluded AI-tool internal state and global `skills/` libraries from project evidence when a tool root such as `~/.qclaw` is passed as a project root.
- Added regression coverage for teammate reports that should keep SmartBI/SCRM evidence while excluding unrelated knowledge-distillation and ads themes.

## 0.2.2

- Changed the default weekly report body to stop at `三、下周计划与需协调事项`; evidence remains in `evidence.json` and the supplement guide instead of a final appendix.
- Added `自主说明` subsections under `一、本周进度与产出` and `二、项目层级推进` so leaders can add missing or corrected context without rewriting scanned summaries.
- Updated the supplement guide to lock scanned section text and remove the default "confirm/supplement/rewrite" prompts for the first two sections.
- Updated smoke tests and regression prompts for the simplified manager-facing flow.

## 0.2.1

- Added TRAE default tool-root discovery for `~/.trae` and `~/.trae-cn`, alongside existing Codex and QClaw defaults.
- Added Claude Code / Claude Desktop default tool-root discovery for `~/.claude`, `~/Library/Application Support/Claude`, and `~/Library/Application Support/Claude-3p`.
- Updated README, SKILL.md, portability guide, and regression prompts to document default TRAE and Claude scanning.

## 0.2.0

- Replaced author-specific initiative and project templates with generic evidence classification for team installs.
- Project-level synthesis now groups the reporter's own files and commits by local project folder, then describes neutral categories such as data/reporting, local custom skills, scripts/automation, content/materials, and document/knowledge outputs.
- Removed embedded personal project maps from the collector source to reduce cross-user leakage when the package is read, copied, or accidentally scanned.
- Updated smoke tests and regression prompts so multi-user portability is tested against generic fixtures rather than the package author's projects.

## 0.1.16

- Reworked evidence collection to exclude generated weekly-report and growth-report artifacts from default progress synthesis, preventing prior reports from being re-read as coworker achievements.
- Added project-local custom `SKILL.md` detection so user-created or iterated skills under explicit project roots appear as conservative progress candidates.
- Added data-analysis/report artifact recall for CSV, Excel, notebook, dashboard, and report files, with conservative wording that asks the leader to confirm analysis object and business use.
- Added regression coverage for a contaminated project root containing historical report text plus real data-analysis and custom-skill files.

## 0.1.15

- Added specific trigger gates for high-risk synthesized initiative and project patterns so generic words like "质量", "回归", or "汇报" do not trigger named template projects.
- Changed project-level rendering to describe current-week action and stage from evidence strength instead of hard-coded personal project status.
- Limited skill attribution in progress bullets to skill names that are explicitly present in the matched evidence.
- Strengthened package self-exclusion so renamed extracted packages are still detected through the local `SKILL.md` frontmatter.
- Added smoke checks for renamed-package scans and generic weekly-report/quality notes.

## 0.1.14

- Excluded the `ai-weekly-progress-report` package's own docs, scripts, templates, tests, fixtures, changelog, and regression prompts from weekly-report evidence synthesis.
- Tightened generated progress and project-level candidates so default achievements require strong project-file or Git evidence, not installed skills or session titles alone.
- Removed test fixtures from the distributable bundle to reduce cross-user leakage risk.
- Added smoke coverage for the case where a coworker scans an installed/extracted skill package as a project root.

## 0.1.13

- Added safe cross-platform top-level project-root preflight before weekly report confirmation.
- Improved recall for project-local crawler, help-center knowledge-base, and visual storyboard / image-generation workflows.
- Preserved weak session-title hits as candidate evidence instead of dropping them when deep session keywords are absent.
- Added Windows and OneDrive Documents root guidance for employees outside macOS.

## 0.1.12

- Added `二、项目层级推进` to the default weekly report structure and moved next-week planning to `三、下周计划与需协调事项`.
- Added project-level candidate synthesis from commits, project files, sessions, and confirmed local evidence signals without treating installed skills alone as project evidence.
- Updated the supplement guide to add a project-level confirmation step before next-week planning.
- Changed the default reporting window from 10 days to 14 days.

## 0.1.11

- Strengthened the interactive confirmation contract: after initialization, the agent must show the generated overall assessment and progress/output draft directly in a fenced `text` block.
- Updated rubric, README, and regression prompts so file links alone are not considered sufficient for first-step review.

## 0.1.10

- Reworked synthesized progress bullets to combine task identification with `能力`、`来源`、`迁移` and `产出/归因`.
- Added evidence-source and transfer descriptions to initiative patterns so weekly progress can show reusable capability without becoming a long growth report.
- Updated rubric, README, and regression prompts for the new progress-item expression contract.

## 0.1.9

- Renamed the weekly opening section to `本周 AI 化总体进展评估`.
- Reworked the weekly opening copy to produce 2-3 management-facing assessment bullets instead of scan-count summaries.
- Kept evidence counts in the appendix and preserved Growth Report Mode for cross-period cognition and capability narratives.
- Updated documentation, regression prompts, and smoke checks for the new opening-section contract.

## 0.1.8

- Simplified the next-step supplement prompt to two fields: `下周计划` and `风险与待支持`.
- Kept the weekly report body structure unchanged while reducing the leader input burden during the second confirmation step.

## 0.1.7

- Reworked Weekly Progress Mode into a traditional management weekly report: summary, `一、本周进度与产出`, `二、下周计划与需协调事项`, and an evidence appendix.
- Removed standalone weekly sections for cognition, Skill/Rules methodology, and project delivery; cognition and management judgment now enter weekly reports only as leader-confirmed context attached to concrete outputs.
- Updated the supplement guide to confirm current-week progress/output first, then next-week plans, while keeping Growth Report Mode unchanged for cross-period cognition and capability narratives.
- Updated weekly report template, rubric, README, test prompts, and smoke checks for the new summary-plus-two-module contract.

## 0.1.6

- Downgraded local installed skill scanning to evidence-only usage: skill assets remain in `evidence.json` but no longer generate a default external-skill subsection in the weekly report body.
- Stopped using installed skill names alone to synthesize module 2 achievements or cognition/methodology conclusions.
- Updated the module 2 supplement prompt to ask for confirmed self-developed, iterated, or actually used workflows, with `evidence.json` skill assets as optional review material only.
- Strengthened regression tests so installed skills do not appear in default report text while nested skill discovery remains covered in `evidence.json`.

## 0.1.5

- Removed the default `团队成员 AI 进度` report module; `members` in the roster is now optional compatibility data and does not drive the standard report body.
- Changed the supervisor workflow to sequential module confirmation: module 1 draft, module 2 draft, module 3 draft, then module 4 next steps.
- Updated `leader-supplement-guide.md` generation so modules 2 and 3 show scan-generated draft previews before asking for confirmation, supplementation, or rewrite.
- Renumbered the standard weekly report to four modules and updated README, rubric, test prompts, and smoke checks accordingly.

## 0.1.4

- Improved module 1 generation so the collector synthesizes cognition/methodology drafts from scan evidence before asking for leader confirmation.
- Added cognition pattern detection for skill quality governance, knowledge production loops, crawler/tool composition, engineering standardization, context-cost efficiency, and data workflow operationalization.
- Updated the supplement guide to show the scan-generated module 1 draft and preview Markdown path before requesting confirmation or edits.
- Strengthened regression expectations so module 1 cannot fall back to blank fill-in prompts or raw evidence counts as the primary insight.

## 0.1.3

- Added `Growth Report Mode` for cross-period AI learning and business practice retrospectives.
- Added growth-report routing rules, evidence layers, default report structure, and conservative attribution boundaries.
- Expanded `references/report-rubric.md` with a dedicated growth report rubric.
- Added README examples for AI growth report prompts and clarified that the collector CLI remains weekly-report focused.
- Added three growth-report regression prompts covering full-history retrospectives, capability-first writing, and weak-evidence boundaries.

## 0.1.0

- Initial V1 skill package.
- Added read-only Git and Codex/QClaw evidence collector.
- Added required team roster, member-by-member supplement flow, Markdown and HTML outputs.
- Added privacy exclusions, report rubric, smoke test, package validator, and bundle builder.

## 0.1.1

- Added leader/team profile initialization and optional local profile memory.
- Added `leader-supplement-guide.md` for step-by-step supervisor confirmation.
- Changed member reporting to exclude the reporting leader by default.
- Split methodology reporting into self-developed workflows and externally installed/synced skills.
- Strengthened non-technical, value-first reporting style with restrained bold headings and attribution notes.

## 0.1.2

- Fixed cross-user evidence attribution so installed skill directories no longer become the installer's self-developed achievements.
- Changed initiative synthesis to use commits, project files, and session signals instead of skill asset names alone.
- Required commit evidence before auto-generating delivery initiatives, reducing leakage of the package author's project history into teammate reports.
- Expanded external skill scanning to recurse through nested skill folders and record up to 300 assets in `evidence.json`.
- Improved folded YAML description parsing for `SKILL.md` frontmatter.
- Added a regression smoke test for installed-skill false positives and nested skill discovery.
