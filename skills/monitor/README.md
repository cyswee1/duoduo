# Monitor Skill 使用指南

## 快速开始

### 1. 安装依赖

```bash
pip install pyyaml pandas openpyxl matplotlib playwright requests
playwright install chromium
```

### 2. 准备凭证文件

创建 `~/.claude/secrets/intro_monitor.env`(路径可在配置中改):

```bash
# BI 系统
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_bi_user
BI_PASS=your_bi_password

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

设置权限:
```bash
chmod 600 ~/.claude/secrets/intro_monitor.env
```

### 3. 运行示例

```bash
cd <skill-dir>/monitor

# phase1(目标登记提醒)
python engine.py examples/weekly_intro_monitor.yaml <团队名> phase1

# phase2(进度监控)
python engine.py examples/weekly_intro_monitor.yaml <团队名> phase2

# phase3(跟进预警)
python engine.py examples/weekly_intro_monitor.yaml <团队名> phase3
```

## 创建自己的监控任务

### 步骤 1:复制范例配置

```bash
cp examples/weekly_intro_monitor.yaml examples/my_monitor.yaml
```

### 步骤 2:修改配置

编辑 `examples/my_monitor.yaml`:

#### 2.1 修改团队信息

```yaml
teams:
  我的团队:
    groups: [A组, B组, C组]
    tl_map:
      A组: {name: TL_A, userid: ""}
      B组: {name: TL_B, userid: ""}
    schedule:
      phase1: "09:00"
      phase2: "11:00"
      phase3: "16:00"
    chatid_key: MY_DINGTALK_CHATID
```

#### 2.2 修改报表配置

```yaml
datasources:
  smartbi:
    reports:
      my_report:
        name: "我的报表名称"
        output_filename: "我的报表.xlsx"
        date_filters: []
```

#### 2.3 修改字段映射

```yaml
phases:
  phase2:
    excel_parsing:
      columns:
        team_group: ['团队', '团队']
        today_count: ['今日', '完成数']
```

#### 2.4 修改阈值

```yaml
phases:
  phase2:
    thresholds:
      progress: 0.75
```

### 步骤 3:运行自定义任务

```bash
python engine.py examples/my_monitor.yaml 我的团队 phase2
```

## 配置文件核心概念

### 硬编码 → 配置化对照表

| 原 weekly_intro_monitor | monitor 模板配置位置 |
|------------------------|-------------------|
| `TEAM_CONFIG` | `teams` |
| `BI_REPORT_PROGRESS` | `datasources.smartbi.reports.progress.name` |
| `PROGRESS_THRESHOLD` | `phases.phase2.thresholds.progress` |
| Excel 列名元组 | `phases.phase2.excel_parsing.columns` |
| 池子列偏移 | `phases.phase3.pool_configs[].column_offset` |
| `TARGET_POOLS` | `phases.phase3.pool_configs[].name` |
| TL 名单 | `teams.*.tl_map` |
| 调度时间 | `teams.*.schedule` |

### 模板变量

- `{this_monday}` — 本周一日期(YYYY-MM-DD)
- `{today}` — 今天日期(YYYY-MM-DD)
- `{team}` — 团队名
- `{unregistered_tls}` — 未登记 TL 列表
- `{deadline}` — 截止时间
- `{table_url}` — 多维表格 URL

## 常见场景

### 场景 1:添加新团队

```yaml
teams:
  新团队:
    groups: [新1组, 新2组]
    tl_map:
      新1组: {name: TL_X, userid: ""}
    schedule:
      phase1: "10:00"
      phase2: "12:00"
    chatid_key: NEW_TEAM_CHATID
```

### 场景 2:修改达标线

```yaml
phases:
  phase2:
    thresholds:
      progress: 0.85
```

### 场景 3:添加新池子

```yaml
phases:
  phase3:
    pool_configs:
      - name: "新池子"
        column_offset: 140
        target: 0.6
```

### 场景 4:修改表格样式

```yaml
phases:
  phase2:
    table_render:
      headers: [小组, 负责人, 目标, 完成, 达标率]
      color_rules:
        - column_index: 4
          condition: "< 0.9"
          color: red
```

## 故障排查

### 问题 1:模块导入失败

```bash
pip list | grep -E 'pyyaml|pandas|playwright'
pip install pyyaml pandas openpyxl matplotlib playwright requests
```

### 问题 2:凭证文件找不到

```bash
ls -la ~/.claude/secrets/intro_monitor.env
chmod 600 ~/.claude/secrets/intro_monitor.env
```

### 问题 3:BI 报表下载失败

- 检查 `BI_URL/BI_USER/BI_PASS` 是否正确
- 检查报表名称是否与 BI 系统中完全一致(包括空格、标点)
- 检查 XPath 是否正确(日期筛选器位置可能变化)

### 问题 4:Excel 解析错误

- 检查 `header_rows` 是否正确(0-based 行号)
- 检查列名元组是否与 Excel 多级表头完全匹配

```python
import pandas as pd
df = pd.read_excel("xxx.xlsx", header=[3, 4])
print(df.columns)
```

### 问题 5:钉钉消息发送失败

- 检查 `DINGTALK_ROBOT_CODE` 是否正确
- 检查 `chatid_key` 对应的 env 变量是否存在
- 检查机器人是否已加入目标群聊

## 进阶用法

### 自定义数据源

在 `datasources/` 下创建新模块:

```python
# datasources/mysql.py
class MySQLDataSource:
    def __init__(self, config, secrets_loader):
        self.config = config
        self.secrets = secrets_loader()

    def query(self, sql):
        pass
```

配置引用:

```yaml
datasources:
  mysql:
    host_key: MYSQL_HOST
    user_key: MYSQL_USER
    pass_key: MYSQL_PASS
```

### 自定义 Phase 类型

在 `engine.py` 的 `run_phase()` 中添加新分支:

```python
elif phase_type == "my_custom_phase":
    self._run_my_custom_phase(team, team_cfg, phase_cfg, chat_id)
```

## 文档

- [SKILL.md](SKILL.md) — 完整功能说明
- [examples/weekly_intro_monitor.yaml](examples/weekly_intro_monitor.yaml) — 完整配置范例
