# Monitor Skill — 可复用的业务监控模板

## 概述

`monitor` 是一个配置驱动的业务监控 skill 模板。通过 YAML 配置文件，可以把 BI 报表、多维表格目标、数据处理、表格渲染和通知推送串成一条自动化监控链路。

### 核心特性

- **配置驱动**：团队、报表、字段、阈值和通知群通过 YAML 配置，无需改代码
- **模块化设计**：数据源、处理器、渲染器、通知器独立可替换
- **凭证安全**：API 密钥、账号密码等敏感信息统一放在本地 env 文件，不进入仓库
- **完整范例**：提供 `examples/weekly_intro_monitor.yaml` 作为可复制的参考模板

---

## 目录结构

```text
.claude/skills/monitor/
├── SKILL.md
├── README.md
├── config_loader.py
├── engine.py
├── requirements.txt
├── datasources/
│   ├── smartbi.py
│   └── notable.py
├── processors/
│   ├── progress.py
│   └── followup.py
├── renderers/
│   └── table_image.py
├── notifiers/
│   └── dingtalk.py
└── examples/
    └── weekly_intro_monitor.yaml
```

详细工作流见 [docs/workflow.md](docs/workflow.md)。

---

## 快速开始

### 1. 准备凭证文件

创建 `~/.claude/secrets/intro_monitor.env`（路径可在 YAML 中修改）：

```bash
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_bi_user
BI_PASS=your_bi_password
BI_SKILL_DIR=/path/to/bi_skill

DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
DINGTALK_ROBOT_CODE=your_robot_code
DINGTALK_MY_USERID=your_userid
DINGTALK_TEST_CHATID=your_chatid

DINGTALK_TABLE_ID=your_table_id
DINGTALK_TABLE_SHEET=your_sheet_id
```

```bash
chmod 600 ~/.claude/secrets/intro_monitor.env
```

### 2. 复制配置范例

```bash
cp examples/weekly_intro_monitor.yaml examples/my_monitor.yaml
```

重点修改这些配置块：

| 配置块 | 说明 |
| --- | --- |
| `teams` | 团队、小组、负责人、通知群和调度时间 |
| `datasources.smartbi.reports` | BI 报表名称、输出文件、筛选条件 |
| `datasources.notable` | 多维表格 ID、字段名、目标字段 |
| `phases` | 每个监控阶段的处理逻辑、阈值、渲染规则 |
| `notifier` | 推送渠道和凭证环境变量名 |
| `globals` | 输出目录、全局池子等共享参数 |

### 3. 运行监控任务

```bash
python engine.py examples/my_monitor.yaml 团队A phase1
python engine.py examples/my_monitor.yaml 团队A phase2
python engine.py examples/my_monitor.yaml 团队A phase3
```

参数说明：

1. `examples/my_monitor.yaml`：配置文件路径。
2. `团队A`：配置中 `teams` 下定义的团队名。
3. `phase1/phase2/phase3`：配置中 `phases` 下定义的阶段名。

---

## 配置文件详解

### 团队配置

```yaml
teams:
  团队A:
    groups: [团队A-1组, 团队A-2组]
    tl_map:
      团队A-1组: {name: TL_A, userid: ""}
      团队A-2组: {name: TL_B, userid: ""}
    schedule:
      phase1: "09:00"
      phase1_deadline: "10:00"
      phase2: "11:30"
      phase3: "16:00"
    chatid_key: DINGTALK_TEST_CHATID
```

### Smartbi 报表配置

```yaml
datasources:
  smartbi:
    url_key: BI_URL
    user_key: BI_USER
    pass_key: BI_PASS
    skill_dir_key: BI_SKILL_DIR
    reports:
      progress:
        name: "示例进度报表"
        output_filename: "progress_monitor.xlsx"
        date_filters: []
        wait_after_open: 5
      followup:
        name: "示例跟进报表"
        output_filename: "followup_monitor.xlsx"
        date_filters:
          - xpath: "YOUR_DATE_FILTER_XPATH"
            value: "{this_monday}"
        wait_after_filter: 60
```

可用模板变量：

- `{this_monday}`：本周一日期（YYYY-MM-DD）
- `{today}`：今天日期（YYYY-MM-DD）

### 多维表格配置

```yaml
datasources:
  notable:
    base_id_key: DINGTALK_TABLE_ID
    sheet_id_key: DINGTALK_TABLE_SHEET
    app_key: DINGTALK_APP_KEY
    app_secret_key: DINGTALK_APP_SECRET
    my_userid_key: DINGTALK_MY_USERID
    table_url_template: "https://alidocs.dingtalk.com/i/nodes/{base_id}?iframeQuery=viewId%3DYOUR_VIEW_ID%26sheetId%3D{sheet_id}"
    team_prefixes:
      团队A: [团队A]
    fields:
      group_name: "小组"
      progress_target: "月度进度目标"
      daily_target: "今日目标"
      pools: "监控池子"
      followup_target: "跟进目标"
    pool_name_mapping:
      "池子A": "池子A"
```

### Phase 1：目标登记提醒

```yaml
phase1:
  type: registration_reminder
  description: "负责人目标登记提醒"
  datasource: notable
  message_template: |
    ### {team} 目标登记提醒

    **未登记负责人**：{unregistered_tls}

    请在 {deadline} 前完成登记：
    [点击打开目标登记表]({table_url})
```

### Phase 2：进度监控

```yaml
phase2:
  type: progress_monitor
  description: "进度监控"
  datasource: smartbi.progress
  notable_datasource: notable
  excel_parsing:
    header_rows: [3, 4]
    columns:
      team_group: ['团队/小组', '团队/小组']
      lp: ['成员', '成员']
      tl: ['负责人', '负责人']
      today_count: ['今日完成情况', '今日完成数']
      monthly_target: ['月度完成情况', '月度目标']
      total_count: ['月度完成情况', '累计完成数']
      today_target: ['今日完成情况', '今日目标']
      monthly_completion_rate: ['月度完成情况', '月度达成率']
  thresholds:
    progress: 0.8
```

### Phase 3：跟进预警

```yaml
phase3:
  type: pool_warning
  description: "跟进预警"
  datasource: smartbi.followup
  pool_configs:
    - name: "池子A"
      column_offset: 22
      target: 0.5
    - name: "池子B"
      column_offset: 50
      target: 0.5
  thresholds:
    call_low: 0.5
```

---

## 扩展指南

### 添加新的数据源

1. 在 `datasources/` 下创建新模块。
2. 实现数据源类，并接收 `config` 和 `secrets_loader`。
3. 在 `engine.py` 中初始化并调用新数据源。

### 添加新的 Phase 类型

1. 在 `processors/` 下创建新处理器。
2. 在 `engine.py` 的 `run_phase()` 中添加新类型分支。
3. 在配置文件中定义新 phase。

### 自定义渲染器

1. 在 `renderers/` 下创建新渲染器。
2. 实现对应的 `render_*` 方法。
3. 在 phase 配置中引用渲染参数。

---

## 常见问题

### 如何调试配置文件？

```python
from config_loader import load_config
cfg = load_config("examples/weekly_intro_monitor.yaml")
print(cfg["teams"]["团队A"])
```

### 如何添加新团队？

在 YAML 的 `teams` 块下添加新团队配置，无需改代码。

### 如何修改表格样式？

修改 `phases.phaseX.table_render` 配置块，或编辑 `renderers/table_image.py`。

### 如何支持其他通知渠道？

在 `notifiers/` 下实现新通知器类，并在 `engine.py` 中注册。
