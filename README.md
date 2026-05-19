# duoduo

个人 Claude Code skills 集合,用于日常运营/数据/业绩自动化。

## 包含的 skills

| Skill | 功能 |
| --- | --- |
| `bi_skill` | Smartbi 报表搜索/导航/下载,支持新旧版导出和多种筛选 |
| `shoutui-update` | 手推链接更新全流程(BI 下载 → 链接生成 → Netlify 部署 → 测试) |
| `weekly_intro_monitor` | 每周转介绍业务监控,自动播报业绩进度并预警 |
| `perf` | 海外思维 LP/TL 转介绍激励计算 |
| `ai-weekly-progress-report` | 基于本地 AI 资产生成周度进度报告 |

## 使用方式

这些 skill 设计为 Claude Code 的 skill 目录加载。把整个 `skills/` 目录链接或复制到 `~/.claude/skills/`,然后在 Claude Code 中通过 `Skill` 工具调用。

```bash
# 示例:链接到 Claude Code skills 目录
ln -s "$(pwd)/skills" ~/.claude/skills
```

## 配置

所有真实凭证通过环境变量注入,**不在代码中硬编码**。

1. 复制 `.env.example` 为 `.env`,填入真实值
2. 加载到当前 shell:`set -a && source .env && set +a`
3. 对于 `weekly_intro_monitor`:复制 `skills/weekly_intro_monitor/team_config_local.example.py` 为 `team_config_local.py`,填入真实 TL 姓名/userid/chatid

## 安全说明

- `.env`、`team_config_local.py`、本地 BI 导出 / Excel / 截图等已通过 `.gitignore` 排除
- 仓库不存放任何真实业务数据、客户/学员信息、合同报价等内容
- 提交前请用 `rg` 扫描凭证关键词,详见 [team-git-github-governance.md](../team-git-github-governance.md)
