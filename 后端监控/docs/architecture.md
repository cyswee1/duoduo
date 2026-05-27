# 功能说明和架构

本文面向接手维护的人，说明后端监控解决什么问题、每个模块负责什么、配置和代码的边界在哪里，以及后续如何扩展。

## 项目目标

后端监控项目用于把分散在 BI 系统、多维表格和通知工具中的监控动作配置化，形成一套可复用的自动化链路：

1. 从配置文件读取团队、报表、字段、阈值和通知规则。
2. 从 Smartbi 或钉钉多维表格拉取数据。
3. 按阶段执行数据处理。
4. 将结果渲染为 Markdown 文本、图片或 HTML。
5. 推送到指定群聊或输出到本地文件。

核心设计目标：业务参数改配置，通用流程留在代码里。

## 架构分层

```text
配置层
  examples/*.yaml
  ~/.claude/secrets/*.env

调度层
  engine.py

数据源层
  datasources/smartbi.py
  datasources/notable.py

处理层
  processors/progress.py
  processors/followup.py

渲染层
  renderers/table_image.py
  templates/dashboard.html

通知层
  notifiers/dingtalk.py
```

## 数据流

```text
YAML 配置 + 本地 env 凭证
        ↓
MonitorEngine 初始化数据源和通知器
        ↓
Smartbi 下载 Excel / Notable 读取目标
        ↓
Processor 按 phase 处理数据
        ↓
Renderer 生成图片或消息内容
        ↓
Notifier 推送到钉钉群
```

## 核心模块

### config_loader.py

负责加载 YAML 配置和凭证文件：

- 读取 `secrets_file` 指向的 env 文件。
- 将真实凭证与仓库配置解耦。
- 解析 `{this_monday}`、`{today}` 等日期模板变量。
- 为引擎提供统一的配置对象和凭证读取函数。

新人接手时重点看：

- `secrets_file` 是否指向正确本地文件。
- env 文件中的 key 是否与 YAML 里的 `*_key` 字段一致。

### engine.py

核心调度入口：

- 解析命令行参数：配置文件、团队名、阶段名。
- 初始化 Smartbi、Notable 和 DingTalk 通知器。
- 根据 `phases.*.type` 分派到对应流程。
- 串联下载、处理、渲染和通知。

当前支持的 phase 类型：

| phase type | 方法 | 作用 |
| --- | --- | --- |
| `registration_reminder` | `_run_registration_reminder` | 检查目标登记并提醒 |
| `progress_monitor` | `_run_progress_monitor` | 计算进度并推送图片 |
| `pool_warning` | `_run_pool_warning` | 识别池子跟进预警并推送图片 |

### datasources/smartbi.py

Smartbi 报表数据源：

- 读取 BI 地址、账号和密码。
- 根据配置打开指定报表。
- 支持日期筛选和等待参数。
- 将报表下载为 Excel。

配置来源：

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
```

需要新增报表时，只要在 `reports` 下新增一个 key，并在 phase 的 `datasource` 中引用，例如 `smartbi.new_report`。

### datasources/notable.py

钉钉多维表格数据源：

- 读取目标登记表。
- 获取团队、小组、目标值、池子配置等业务输入。
- 支持通过 `team_prefixes` 控制不同团队读取哪些小组。
- 支持通过 `pool_name_mapping` 统一池子名称。

配置来源：

```yaml
datasources:
  notable:
    base_id_key: DINGTALK_TABLE_ID
    sheet_id_key: DINGTALK_TABLE_SHEET
    team_prefixes:
      团队A: [团队A]
    fields:
      group_name: "小组"
      progress_target: "月度进度目标"
      daily_target: "今日目标"
      pools: "监控池子"
```

新人接手时重点确认：多维表格字段名改了以后，必须同步更新 `fields`。

### processors/progress.py

进度监控处理器：

- 解析多级表头 Excel。
- 按团队/小组汇总今日完成、月度完成和目标。
- 排除负责人行、总计行和空行。
- 计算今日达标率、月进度和 GAP。

关键配置：

```yaml
excel_parsing:
  header_rows: [3, 4]
  columns:
    team_group: ['团队/小组', '团队/小组']
    lp: ['成员', '成员']
    tl: ['负责人', '负责人']
    today_count: ['今日完成情况', '今日完成数']
    total_count: ['月度完成情况', '累计完成数']
```

如果 BI 报表格式变化，通常只需要改 `header_rows` 和 `columns`。

### processors/followup.py

跟进预警处理器：

- 按池子配置读取不同列段。
- 从 Excel 中按 `column_offset` 找到实际跟进率。
- 与目标阈值对比。
- 输出未达标或无数据预警行。

关键配置：

```yaml
pool_configs:
  - name: "池子A"
    column_offset: 22
    target: 0.5
```

如果 BI 报表新增或移动池子列，优先更新 `pool_configs`，不要改处理器代码。

### renderers/table_image.py

表格图片渲染器：

- 根据 `table_render.headers` 生成表格。
- 根据 `color_rules` 对重点单元格标色。
- 输出可被通知器发送的图片字节流。

配置来源：

```yaml
table_render:
  title_template: "【进度监控 — {team}】"
  headers: [小组, 负责人, 今日目标, 今日完成, 今日达标率, 月目标, 月完成, 月进度, GAP]
  color_rules:
    - column_index: 4
      condition: "< 0.8"
      color: red
```

### templates/dashboard.html

HTML 展示模板：

- 当前作为静态展示模板保留。
- 可用于后续把监控结果生成网页、日报或看板。
- 模板通过 `{{TITLE}}`、`{{TEAM}}`、`{{PHASE}}`、`{{TABLE_ROWS}}` 等占位符注入内容。

### notifiers/dingtalk.py

钉钉通知器：

- 获取 access token。
- 按 chatid 发送文本、Markdown 或图片消息。
- 支持通过配置控制目标群。

配置来源：

```yaml
notifier:
  type: dingtalk_robot
  robot_code_key: DINGTALK_ROBOT_CODE
  app_key: DINGTALK_APP_KEY
  app_secret_key: DINGTALK_APP_SECRET
```

目标群来自团队配置：

```yaml
teams:
  团队A:
    chatid_key: DINGTALK_TEST_CHATID
```

## 配置接口

完整配置由六个主要部分组成：

```yaml
name: monitor_name
secrets_file: ~/.claude/secrets/intro_monitor.env

teams: {}
datasources: {}
phases: {}
notifier: {}
globals: {}
```

### teams

配置团队、小组、负责人、阶段时间和通知群。

必填字段：

- `groups`：该团队下需要监控的小组列表。
- `tl_map`：小组到负责人姓名和 userid 的映射。
- `schedule`：每个 phase 的运行时间和 deadline。
- `chatid_key`：env 文件中的群聊 ID 变量名。

### datasources

配置所有外部数据源，例如 BI 报表、多维表格、未来可扩展的数据库或 API。

### phases

配置每个监控阶段的业务类型、输入数据源、字段映射、阈值、渲染规则和消息模板。

### notifier

配置通知渠道。当前示例使用钉钉机器人，也可以扩展到企业微信、飞书、邮件等渠道。

### globals

放置输出目录、全局池子、默认参数等多个阶段共用的配置。

## 修改场景

### 添加新团队

1. 在 `teams` 下新增团队。
2. 填写 `groups`、`tl_map`、`schedule`、`chatid_key`。
3. 在 `datasources.notable.team_prefixes` 中增加团队前缀。
4. 用测试群跑三个 phase。

### 替换 BI 报表

1. 修改 `datasources.smartbi.reports.*.name`。
2. 如果导出文件名变化，修改 `output_filename`。
3. 如果筛选器变化，修改 `date_filters`。
4. 如果 Excel 表头变化，修改 `phases.*.excel_parsing`。

### 修改阈值

1. 进度阈值改 `phases.phase2.thresholds.progress`。
2. 跟进阈值改 `phases.phase3.thresholds.call_low` 或 `pool_configs[].target`。
3. 表格高亮规则改 `table_render.color_rules`。

### 添加新池子

1. 在 `datasources.notable.pool_name_mapping` 中增加池子名称映射。
2. 在 `phases.phase3.pool_configs` 中新增池子配置。
3. 确认 `column_offset` 对应 Excel 中正确列。
4. 跑 `phase3` 验证预警结果。

## 扩展方式

### 增加新数据源

1. 在 `datasources/` 下新增模块。
2. 实现读取方法，并接收 `config` 和 `secrets_loader`。
3. 在 `engine.py` 中按配置注册。
4. 在 YAML 的 `datasources` 中新增配置块。

### 增加新监控阶段

1. 在 `processors/` 下新增处理器。
2. 在 `engine.py` 中增加 `phase_type` 分支。
3. 在 YAML 的 `phases` 中定义新阶段。
4. 在 README 和 workflow 文档中补充使用方式。

### 增加新通知渠道

1. 在 `notifiers/` 下新增通知器。
2. 读取配置中的凭证 key。
3. 在 `notifier.type` 中切换渠道。
4. 在 env 文件中添加对应凭证。

## 安全设计

- 真实凭证只放在本地 env 文件，不提交到仓库。
- 配置范例只保留占位符、示例团队和示例 ID。
- 本地下载的 Excel、截图、日志和导出文件应加入 `.gitignore`。
- 上传公开仓库前必须扫描 token、密码、内部域名、真实姓名、真实业务数据和个人路径。
- 新人接手时如发现真实凭证曾经进入 GitHub，应立即轮换凭证。
