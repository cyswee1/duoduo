---
name: weekly_intro_monitor
description: 每周转介绍业务监控 — 每周二/三自动提醒TL登记目标、播报业绩进度、预警外呼跟进不足，支持手动触发
user-invocable: true
allowed-tools:
  - Bash(python3 *)
  - Bash(pip3 install *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Write
  - Edit
---

# 每周转介绍业务监控

每周二/三按团队分时段执行三个阶段：提醒TL登记目标、业绩进度播报、外呼跟进预警。

## 触发方式

用户说「转介绍监控」「业务监控」「播报」或调用 `/weekly_intro_monitor`。

## 前置准备

```bash
python3 -c "import playwright; import pandas; import openpyxl; import requests" 2>&1 || pip3 install playwright pandas openpyxl requests
```

脚本路径：`.claude/skills/weekly_intro_monitor/monitor.py`

## 执行命令

```bash
# 执行指定阶段
python3 .claude/skills/weekly_intro_monitor/monitor.py phase1 --team 美澳
python3 .claude/skills/weekly_intro_monitor/monitor.py phase2 --team 美澳
python3 .claude/skills/weekly_intro_monitor/monitor.py phase3 --team 美澳

# 执行全部阶段
python3 .claude/skills/weekly_intro_monitor/monitor.py all --team 美澳

# 强制执行（跳过周二/三检查）
python3 .claude/skills/weekly_intro_monitor/monitor.py all --team 美澳 --force
```

参数：
- `phase1` / `phase2` / `phase3` / `all`：执行阶段
- `--team`：团队类型（美澳 / 港澳），必填
- `--force`：跳过日期检查，强制执行
- `--dry-run`：只计算不发送，输出到终端

## 执行时间规则

| 团队 | 阶段1（提醒登记） | 阶段2/3（播报+预警） |
|------|------------------|---------------------|
| 美澳 | 08:00 | 11:30 / 14:00 / 16:00 |
| 港澳 | 12:00 | 14:00 / 16:00 / 18:00 |

仅周二/三自动执行，手动触发时加 `--force` 跳过日期检查。

## 三个阶段

### 阶段1：提醒TL登记目标

向钉钉群发送登记提醒卡片，@对应团队所有TL。

### 阶段2：业绩进度播报

1. 从 BI 下载业绩播报报表(报表名通过环境变量 `BI_REPORT_PROGRESS` 配置,当日 + 池子过滤)
2. 从钉钉多维表格读取TL登记的今日目标
3. 计算进度和GAP：
   - 今日达成进度 = 今日例子数 / 今日例子目标
   - GAP = roundup(小组进度目标% × 海外转介绍例子目标 - 全体带海外例子数)
4. 标记达成进度 < 80% 的LP/小组
5. 发送 markdown 播报到钉钉群

### 阶段3：外呼跟进预警

1. 从 BI 下载外呼跟进报表(报表名通过环境变量 `BI_REPORT_FOLLOWUP` 配置,当周周一~当日 + 池子过滤)
2. 按池子分组计算外呼跟进率
3. 标记低于阈值的小组/LP
4. 分池子发送预警到钉钉群

## 监控池子（固定）

- M1-M3（首消）
- 续费带R
- 服务池

## 全局规则

- 不允许修改目标池子
- 不允许修改核心阈值（除非配置调整）
- 所有BI下载必须带时间范围和池子过滤
- 每次输出必须@对应TL
- 港澳团队12点前不执行阶段1
- 美澳团队8点前不执行任何提醒

## 关键实现细节

- BI下载复用 `bi_skill.py` 的 `_apply_date_filter_v2`、`_apply_multiselect_filter`、`_do_export` 函数
- 钉钉发送使用企业内部应用API（需 corpid/corpsecret/agentid/chatid）
- TL目标数据从钉钉多维表格API读取
- 图片表格通过 matplotlib/pandas 生成后上传钉钉媒体文件
