# Monitor Skill — 可复用的业务监控模板

## 概述

`monitor` 是一个**配置驱动**的业务监控 skill 模板，从 `weekly_intro_monitor` 抽象而来。通过 YAML 配置文件，可以快速复用到其他类似的监控场景。

### 核心特性

- **配置驱动**：所有业务逻辑（团队、报表、字段、阈值）通过 YAML 配置，无需改代码
- **模块化设计**：数据源、处理器、渲染器、通知器独立可替换
- **凭证安全**：所有敏感信息（API 密钥、数据库密码）统一存放在 `~/.claude/secrets/` 目录
- **完整范例**：提供 `weekly_intro_monitor.yaml` 作为可运行的参考模板

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
│   └── followup.py                   # 外呼跟进预警提取
├── renderers/                        # 渲染器
│   └── table_image.py                # 表格图片渲染（matplotlib）
├── notifiers/                        # 通知器
│   └── dingtalk.py                   # 钉钉机器人通知
└── examples/                         # 配置范例
    └── weekly_intro_monitor.yaml     # 完整复现原 skill 的配置
```

---

## 快速开始

### 1. 准备凭证文件

创建 `~/.claude/secrets/intro_monitor.env`（或其他名称），写入所需凭证：

```bash
# BI 系统
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_user
BI_PASS=your_password

# 钉钉 API
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
DINGTALK_ROBOT_CODE=your_robot_code
DINGTALK_MY_USERID=your_userid
DINGTALK_TEST_CHATID=your_chatid

# 钉钉多维表格
DINGTALK_TABLE_ID=your_table_id
DINGTALK_TABLE_SHEET=your_sheet_id
```

设置权限：
```bash
chmod 600 ~/.claude/secrets/intro_monitor.env
```

### 2. 编写配置文件

参考 `examples/weekly_intro_monitor.yaml`，创建你的配置文件。核心结构：

```yaml
name: my_monitor
secrets_file: ~/.claude/secrets/my_monitor.env

teams:
  团队A:
    groups: [A1组, A2组]
    tl_map:
      A1组: {name: 张三, userid: ""}
    schedule:
      phase1: "09:00"
      phase2: "11:00"
    chatid_key: DINGTALK_CHATID_A

datasources:
  smartbi:
    url_key: BI_URL
    user_key: BI_USER
    pass_key: BI_PASS
    reports:
      my_report:
        name: "报表名称"
        output_filename: "输出文件.xlsx"
        date_filters: []

  notable:
    base_id_key: DINGTALK_TABLE_ID
    sheet_id_key: DINGTALK_TABLE_SHEET
    fields:
      group_name: "小组"
      progress_target: "进度目标"

phases:
  phase1:
    type: registration_reminder
    datasource: notable
    message_template: |
      ### 提醒标题
      内容...

  phase2:
    type: progress_monitor
    datasource: smartbi.my_report
    excel_parsing:
      header_rows: [3, 4]
      columns:
        team_group: ['团队/小组', '团队/小组']
        today_count: ['今日完成情况', '今日例子数']
    thresholds:
      progress: 0.8
    table_render:
      title_template: "【监控标题 — {team}团队】"
      headers: [小组, TL, 今日目标, 今日例子, 达标率]
      color_rules:
        - column_index: 4
          condition: "< 0.8"
          color: red

notifier:
  type: dingtalk_robot
  robot_code_key: DINGTALK_ROBOT_CODE
  app_key: DINGTALK_APP_KEY
  app_secret_key: DINGTALK_APP_SECRET

globals:
  output_dir: ~/Downloads
```

### 3. 运行监控任务

```bash
cd <skill-dir>/monitor
python engine.py examples/weekly_intro_monitor.yaml 美澳 phase2
```

参数说明：
- 第1个参数：YAML 配置文件路径
- 第2个参数：团队名（必须在 `teams` 中定义）
- 第3个参数：阶段名（必须在 `phases` 中定义）

---

## 配置文件详解

### 1. 团队配置 (`teams`)

定义监控的团队、小组、TL 信息和调度时间。

```yaml
teams:
  美澳:
    groups: [美澳1组, 美澳2组, 美澳3组]  # 小组列表
    tl_map:                              # TL 映射
      美澳1组:
        name: TL_A                        # TL 姓名
        userid: ""                       # 钉钉 userid（用于 @ 提醒）
    schedule:                            # 调度时间
      phase1: "09:00"
      phase1_deadline: "10:00"
      phase2: "11:30"
      phase3: "16:00"
    chatid_key: DINGTALK_TEST_CHATID     # 群聊 ID 的 env key
```

### 2. 数据源配置 (`datasources`)

#### Smartbi BI 报表

```yaml
datasources:
  smartbi:
    url_key: BI_URL                      # BI 系统 URL 的 env key
    user_key: BI_USER                    # 用户名的 env key
    pass_key: BI_PASS                    # 密码的 env key
    reports:
      progress:                          # 报表标识（自定义）
        name: "转介绍益智业绩播报_LP维度_末次渠道"  # BI 中的报表名称
        output_filename: "业绩播报_监控.xlsx"      # 下载后的文件名
        date_filters: []                 # 日期筛选（空表示无筛选）
        wait_after_open: 5               # 打开报表后等待秒数
      followup:
        name: "思维转介绍过程跟进报表_末次渠道"
        output_filename: "外呼跟进_监控.xlsx"
        date_filters:                    # 日期筛选配置
          - xpath: "/html/body/..."      # 输入框的 XPath
            value: "{this_monday}"       # 模板变量（自动解析）
        wait_after_filter: 60            # 筛选后等待秒数
```

**模板变量**：
- `{this_monday}`：本周一日期（YYYY-MM-DD）
- `{today}`：今天日期（YYYY-MM-DD）

#### 钉钉多维表格（Notable）

```yaml
datasources:
  notable:
    base_id_key: DINGTALK_TABLE_ID       # 表格 ID 的 env key
    sheet_id_key: DINGTALK_TABLE_SHEET   # sheet ID 的 env key
    app_key: DINGTALK_APP_KEY
    app_secret_key: DINGTALK_APP_SECRET
    my_userid_key: DINGTALK_MY_USERID
    table_url_template: "https://alidocs.dingtalk.com/i/nodes/{base_id}?..."
    fields:                              # 字段映射
      group_name: "小组"                  # Notable 中的字段名
      progress_target: "转介绍例子进度目标"
      daily_target: "今日例子目标"
      pools: "跟进池子"
      followup_target: "外呼跟进目标"
    pool_name_mapping:                   # 池子名称映射
      "M1-M3": "M1-M3（首消）"
```

### 3. 阶段配置 (`phases`)

#### Phase 1: 目标登记提醒 (`registration_reminder`)

```yaml
phases:
  phase1:
    type: registration_reminder
    description: "TL 目标登记提醒"
    datasource: notable                  # 使用 notable 数据源
    message_template: |                  # 消息模板
      ### 📋 {team} 转介绍目标登记提醒
      
      **未登记 TL**：{unregistered_tls}
      
      请在 {deadline} 前完成登记：
      [👉 点击打开目标登记表]({table_url})
```

**模板变量**：
- `{team}`：团队名
- `{unregistered_tls}`：未登记 TL 列表（逗号分隔）
- `{deadline}`：截止时间
- `{table_url}`：多维表格 URL

#### Phase 2: 业绩进度监控 (`progress_monitor`)

```yaml
phases:
  phase2:
    type: progress_monitor
    description: "业绩进度监控"
    datasource: smartbi.progress         # 使用 smartbi 的 progress 报表
    notable_datasource: notable          # 同时需要 notable 读取目标
    excel_parsing:                       # Excel 解析配置
      header_rows: [3, 4]                # 多级表头行号（0-based）
      columns:                           # 列名映射（多级表头用元组）
        team_group: ['团队/小组', '团队/小组']
        lp: ['LP', 'LP']
        tl: ['负责人', '负责人']
        today_count: ['今日完成情况', '今日例子数']
        monthly_target: ['海外转介绍例子数据', '海外转介绍例子目标']
        total_count: ['海外转介绍例子数据', '全体带海外例子数']
        today_target: ['今日完成情况', '今日例子目标']
        monthly_completion_rate: ['海外转介绍例子数据', '例子达成率-月度']
    thresholds:                          # 阈值配置
      progress: 0.8                      # 进度达标线
    table_render:                        # 表格渲染配置
      title_template: "【转介绍业绩进度监控 — {team}团队】"
      headers: [小组, TL, 今日目标, 今日例子, 今日达标率, 月目标, 月例子, 月进度, GAP]
      color_rules:                       # 颜色规则
        - column_index: 4                # 列索引（0-based）
          condition: "< 0.8"             # 条件表达式
          color: red                     # 颜色
        - column_index: 8
          condition: "> 0"
          color: red
```

#### Phase 3: 外呼跟进预警 (`pool_warning`)

```yaml
phases:
  phase3:
    type: pool_warning
    description: "外呼跟进预警"
    datasource: smartbi.followup
    pool_configs:                        # 池子配置
      - name: "续费带R"                   # 池子名称
        column_offset: 22                # Excel 列偏移
        target: 0.5                      # 目标跟进率
      - name: "M1-M3（首消）"
        column_offset: 50
        target: 0.5
      - name: "服务池"
        column_offset: 112
        target: 0.5
    thresholds:
      call_low: 0.5
      min_call_with_zero_conversion: 10
    table_render:
      title_template: "【转介绍外呼跟进监控 — {team}团队】"
      headers: [小组, 池子, 实际跟进率, 目标, 状态]
      color_rules:
        - column_index: 2
          condition: "status == '未达标'"
          color: red
        - column_index: 4
          condition: "status == '未达标'"
          color: red
```

### 4. 通知器配置 (`notifier`)

```yaml
notifier:
  type: dingtalk_robot
  robot_code_key: DINGTALK_ROBOT_CODE    # 机器人 code 的 env key
  app_key: DINGTALK_APP_KEY
  app_secret_key: DINGTALK_APP_SECRET
```

### 5. 全局配置 (`globals`)

```yaml
globals:
  output_dir: ~/Downloads                # BI 报表下载目录
  target_pools: ["M1-M3（首消）", "续费带R", "服务池"]  # 全局池子列表
```

---

## 扩展指南

### 添加新的数据源

1. 在 `datasources/` 下创建新模块（如 `mysql.py`）
2. 实现数据源类，提供统一的读取接口
3. 在 `engine.py` 中注册新数据源类型

### 添加新的 Phase 类型

1. 在 `processors/` 下创建新处理器
2. 在 `engine.py` 的 `run_phase()` 中添加新类型分支
3. 在配置文件中定义新 phase

### 自定义渲染器

1. 在 `renderers/` 下创建新渲染器
2. 实现 `render_xxx_table()` 方法
3. 在 phase 配置中指定渲染器类型

---

## 与原 weekly_intro_monitor 的对比

| 项目 | weekly_intro_monitor | monitor 模板 |
|------|---------------------|-------------|
| 团队配置 | 硬编码在 config.py | YAML 配置 |
| 报表名称 | 硬编码在 config.py | YAML 配置 |
| 字段映射 | 硬编码在 monitor.py | YAML 配置 |
| 阈值参数 | 硬编码在 config.py | YAML 配置 |
| 池子列偏移 | 硬编码在 monitor.py | YAML 配置 |
| 凭证管理 | 部分在 config.py | 全部在 env 文件 |
| 扩展性 | 需改代码 | 改配置即可 |

---

## 常见问题

### Q: 如何调试配置文件？

A: 使用 Python 交互式环境加载配置：

```python
from config_loader import load_config
cfg = load_config("examples/weekly_intro_monitor.yaml")
print(cfg["teams"]["美澳"])
```

### Q: 如何添加新团队？

A: 在 YAML 的 `teams` 块下添加新团队配置，无需改代码。

### Q: 如何修改表格样式？

A: 修改 `phases.phaseX.table_render` 配置块，或直接编辑 `renderers/table_image.py`。

### Q: 如何支持其他通知渠道（如企业微信、飞书）？

A: 在 `notifiers/` 下实现新通知器类，在 `engine.py` 中注册。

---

## 许可

本模板基于 `weekly_intro_monitor` skill 抽象而来，供内部使用。
