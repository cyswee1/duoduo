# Monitor Skill — 可复用的业务监控模板

## 概述

`monitor` 是一个**配置驱动**的业务监控 skill 模板，从 `weekly_intro_monitor` 抽象而来。通过 YAML 配置文件，可以快速复用到其他类似的监控场景。

### 核心特性

- **配置驱动**：所有业务逻辑（团队、报表、字段、阈值）通过 YAML 配置，无需改代码
- **模块化设计**：数据源、处理器、渲染器、通知器独立可替换
- **凭证安全**：所有敏感信息（API 密钥、数据库密码）统一存放在 `~/.claude/secrets/` 目录，也支持环境变量覆盖到临时 env 文件
- **完整范例**：提供 `weekly_intro_monitor.yaml` 作为可运行的参考模板
- **云端调度**：支持通过 GitHub Actions 在云端定时执行，不依赖本地机器常驻

---

## 目录结构

```
.claude/skills/monitor/
├── SKILL.md                          # 本文档
├── config_loader.py                  # YAML 配置加载器
├── engine.py                         # 核心调度引擎
├── datasources/                      # 数据源模块
│   ├── smartbi.py                    # Smartbi BI 报表下载
│   └── notable.py                    # 钉钉多维表格读取
├── processors/                       # 数据处理器
│   ├── progress.py                   # 业绩进度计算
│   ├── followup.py                   # 外呼跟进预警提取
│   ├── renewal.py                    # 续费预警处理
│   └── service.py                    # 服务预警处理
├── renderers/                        # 渲染器
│   └── table_image.py                # 表格图片渲染（matplotlib）
├── notifiers/                        # 通知器
│   └── dingtalk.py                   # 钉钉机器人通知
├── generated/                        # 场景配置
│   ├── intro_monitor.yaml
│   ├── renewal_monitor.yaml
│   └── service_monitor.yaml
└── dispatch.py                       # 动态调度入口
```

---

## 快速开始

### 1. 准备凭证文件

默认创建 `~/.claude/secrets/intro_monitor.env`（或其他名称），写入所需凭证：

```bash
# BI 系统
BI_URL=https://bi.61info.cn/smartbi/vision/index.jsp
BI_USER=your_user
BI_PASS=your_password

# 钉钉 API
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
DINGTALK_ROBOT_CODE=your_robot_code
DINGTALK_MY_USERID=your_userid
DINGTALK_TEST_CHATID=your_chatid

# 钉钉多维表格 / 群 webhook（按场景补充）
DINGTALK_GANGAO_CHATID=your_chatid
DINGTALK_XUEGUAN_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_GANGAO_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=yyy
```

设置权限：

```bash
chmod 600 ~/.claude/secrets/intro_monitor.env
```

> 也可以通过环境变量 `MONITOR_SECRETS_FILE` 指向任意临时 env 文件，适合 GitHub Actions / CI 使用。

### 2. 运行监控任务

```bash
cd /Users/dory/Desktop/claude/.claude/skills/monitor
python engine.py generated/intro_monitor.yaml 美澳 phase2
python dispatch.py 港澳 target_confirm
```

参数说明：
- `engine.py <config.yaml> <team> <phase>`：直接运行指定场景和阶段
- `dispatch.py <team> <phase_type>`：按团队和业务入口动态调度

---

## 云端 / CI 运行

### 环境变量覆盖

monitor 支持以下环境变量，便于 GitHub Actions 或其他 CI 环境调用：

- `MONITOR_SECRETS_FILE`：覆盖 YAML 中的 `secrets_file`
- `MONITOR_OUTPUT_DIR`：覆盖 YAML 中的 `globals.output_dir`
- `MONITOR_SMARTBI_HEADLESS`：控制 Smartbi Playwright 是否无头运行（`true/false`）
- `MONITOR_SMARTBI_BROWSER_CHANNEL`：指定浏览器 channel；不设置时使用 Playwright 自带 Chromium

本地默认仍可沿用：
- secrets 文件：`~/.claude/secrets/...`
- 输出目录：`~/Downloads`

### GitHub Actions 定时调度

仓库中提供工作流：
- `.github/workflows/monitor-schedule.yml`

作用：
- 支持 `workflow_dispatch` 手动触发代表性监控任务
- 支持 `schedule` 每日定时执行美澳 / 港澳的目标确认与 phase2 播报
- 在 runner 上临时生成 secrets env 文件并注入 monitor

### 需要配置的 GitHub Secrets

至少需要：

```text
BI_URL
BI_USER
BI_PASS
DINGTALK_APP_KEY
DINGTALK_APP_SECRET
DINGTALK_ROBOT_CODE
DINGTALK_MY_USERID
DINGTALK_TEST_CHATID
DINGTALK_GANGAO_CHATID
DINGTALK_XUEGUAN_WEBHOOK
DINGTALK_GANGAO_WEBHOOK
```

如果 notable / 其他场景还依赖额外密钥，也一并加入 repo secrets。

### GitHub Actions 使用建议

1. 先用 `workflow_dispatch` 手动跑 2~3 个任务
2. 确认 Smartbi 在云端可访问、无验证码/风控问题
3. 确认钉钉发送正常
4. 再开启正式每日 schedule

> 注意：GitHub Actions 的 cron 使用 UTC，且可能比设定时间晚几分钟触发，属于平台特性。

---

## 配置文件说明

### 团队配置 (`teams`)

```yaml
teams:
  美澳:
    groups: [美澳1组, 美澳2组, 美澳3组]
    tl_map:
      美澳1组:
        name: 刘洋
        userid: "1625453324939147"
        mobile: "15754047099"
    schedule:
      phase1: "09:00"
      phase1_deadline: "10:00"
      phase2: "11:30"
    chatid_key: DINGTALK_TEST_CHATID
    webhook_key: DINGTALK_XUEGUAN_WEBHOOK
```

> 配置了 `webhook_key` 的团队走 webhook，@人需要 `mobile`。
> 未配置 `webhook_key` 的团队走企业应用，@人使用 `userid`。

### Smartbi 配置 (`datasources.smartbi`)

```yaml
datasources:
  smartbi:
    url_key: BI_URL
    user_key: BI_USER
    pass_key: BI_PASS
    headless: false          # 可选；CI 建议由环境变量控制
    browser_channel: chrome  # 可选；CI 不设更稳
    reports:
      progress:
        name: "转介绍益智业绩播报_LP维度_末次渠道"
        output_filename: "业绩播报_监控.xlsx"
        date_filters: []
```

### 全局配置 (`globals`)

```yaml
globals:
  output_dir: ~/Downloads
```

> 云端运行时推荐用 `MONITOR_OUTPUT_DIR` 覆盖到 runner 临时目录。

---

## 运行守卫说明

- `engine.py` 会按场景读取“核心目标字段”，只有存在**非空非零目标**时才发送 phase2/phase3。
- 美澳目标默认读 OA 日志；若当天多维表格有更新，则按小组覆盖。
- 港澳目标默认读多维表格。
- 这样可以避免“没填目标也乱发播报”的问题。

---

## 常见问题

### Q: 如何调试配置文件？

```python
from config_loader import load_config
cfg = load_config("generated/intro_monitor.yaml")
print(cfg["teams"]["美澳"])
```

### Q: GitHub Actions 上跑不通 Smartbi 怎么办？

优先检查：
- BI 是否允许公网访问
- 是否出现验证码 / 登录风控
- Playwright headless 是否导致页面行为差异

如果 GitHub-hosted runner 不稳定，建议切到：
- self-hosted runner
- 或云服务器 cron

### Q: 如何支持其他通知渠道（如企业微信、飞书）？

在 `notifiers/` 下实现新通知器类，在 `engine.py` 中注册。

---

## 许可

本模板基于 `weekly_intro_monitor` skill 抽象而来，供内部使用。