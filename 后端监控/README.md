# 后端监控

后端监控是一个配置驱动的业务监控项目模板，用于把 BI 报表、多维表格目标、数据处理、表格渲染和通知推送串成一条自动化监控链路。交接给下一个人时，对方按本文从上到下操作，就能完成环境准备、配置替换、试跑和上线检查。

## 适用场景

- 每天或每周固定检查团队目标登记情况。
- 从 Smartbi 下载进度或跟进类 Excel 报表。
- 从钉钉多维表格读取小组目标、负责人和监控池子。
- 计算达标率、进度缺口或跟进预警。
- 渲染表格图片，并通过钉钉机器人推送到指定群。

## 目录结构

```text
后端监控/
├── README.md                         # 使用指南和交接说明
├── config_loader.py                  # YAML 配置加载与凭证加载
├── engine.py                         # 核心调度引擎
├── requirements.txt                  # Python 依赖
├── datasources/                      # 数据源模块
│   ├── smartbi.py                    # Smartbi 报表下载
│   └── notable.py                    # 钉钉多维表格读取
├── processors/                       # 数据处理模块
│   ├── progress.py                   # 进度监控计算
│   └── followup.py                   # 跟进预警计算
├── renderers/                        # 结果渲染模块
│   └── table_image.py                # 表格图片渲染
├── notifiers/                        # 通知模块
│   └── dingtalk.py                   # 钉钉机器人推送
├── examples/
│   └── weekly_intro_monitor.yaml     # 完整配置范例
├── templates/
│   └── dashboard.html                # HTML 展示模板
└── docs/
    ├── architecture.md               # 功能说明和架构
    └── workflow.md                   # 详细工作流程
```

## 快速上手

### 1. 进入项目目录

```bash
cd 后端监控
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

依赖用途：

| 依赖 | 用途 |
| --- | --- |
| `pyyaml` | 读取 YAML 配置 |
| `pandas` / `openpyxl` | 解析 Excel 报表 |
| `matplotlib` | 渲染表格图片 |
| `playwright` | 驱动浏览器下载 Smartbi 报表 |
| `requests` | 调用钉钉 API |

### 3. 准备本地凭证

创建本地 env 文件，默认路径来自配置文件的 `secrets_file`：

```bash
~/.claude/secrets/intro_monitor.env
```

文件内容示例：

```bash
# BI 系统
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_bi_user
BI_PASS=your_bi_password
BI_SKILL_DIR=/path/to/bi_skill

# 钉钉机器人和开放平台
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

注意：真实账号、密码、token、群 ID、表格 ID 只放在本地 env 文件，不要提交到 GitHub。

### 4. 复制配置范例

```bash
cp examples/weekly_intro_monitor.yaml examples/my_monitor.yaml
```

### 5. 修改配置

优先修改这些配置块：

| 配置块 | 必填内容 | 示例位置 |
| --- | --- | --- |
| `teams` | 团队、小组、负责人、通知群 env key、阶段时间 | `teams.团队A` |
| `datasources.smartbi.reports` | BI 报表名称、导出文件名、日期筛选器 | `reports.progress` / `reports.followup` |
| `datasources.notable` | 多维表格字段名、团队前缀、池子映射 | `fields` / `team_prefixes` |
| `phases.phase1` | 目标登记提醒消息模板 | `message_template` |
| `phases.phase2` | 进度报表表头行、列名、阈值、表格样式 | `excel_parsing` |
| `phases.phase3` | 池子列偏移、目标值、阈值、表格样式 | `pool_configs` |
| `notifier` | 钉钉机器人凭证 env key | `robot_code_key` |
| `globals` | 输出目录、全局池子 | `output_dir` |

### 6. 试跑三个阶段

先使用测试群的 `chatid_key`，确认消息格式无误后再切换到正式群。

```bash
# Phase 1：目标登记提醒
python engine.py examples/my_monitor.yaml 团队A phase1

# Phase 2：进度监控
python engine.py examples/my_monitor.yaml 团队A phase2

# Phase 3：跟进预警
python engine.py examples/my_monitor.yaml 团队A phase3
```

命令参数说明：

1. `examples/my_monitor.yaml`：配置文件路径。
2. `团队A`：必须存在于 YAML 的 `teams` 下。
3. `phase1/phase2/phase3`：必须存在于 YAML 的 `phases` 下。

## 三个阶段做什么

### Phase 1：目标登记提醒

读取多维表格中的登记记录，对比 `teams.*.tl_map` 中应登记的负责人，找出未登记目标的人，并向配置群发送 Markdown 提醒。

### Phase 2：进度监控

下载 Smartbi 进度报表，读取多维表格中的今日目标和月度进度目标，按小组计算今日达标率、月度完成率和 GAP，并渲染成图片推送。

### Phase 3：跟进预警

下载 Smartbi 跟进报表，读取每个小组需要监控的池子，按 `pool_configs[].column_offset` 找到对应列，计算实际跟进率并推送未达标预警。

## 配置化原则

项目把原本容易硬编码的内容全部放到 YAML 或环境变量中：

| 内容 | 配置位置 |
| --- | --- |
| 团队和小组 | `teams` |
| 负责人和 userid | `teams.*.tl_map` |
| BI 地址、账号、密码 | `secrets_file` 对应 env 文件 |
| BI 报表名称 | `datasources.smartbi.reports.*.name` |
| BI 日期筛选器 | `datasources.smartbi.reports.*.date_filters` |
| Excel 表头行和字段名 | `phases.*.excel_parsing` |
| 达标阈值 | `phases.*.thresholds` |
| 池子名称和列偏移 | `phases.phase3.pool_configs` |
| 多维表格字段名 | `datasources.notable.fields` |
| 通知群 | `teams.*.chatid_key` |
| 表格样式 | `phases.*.table_render` |

## 新人交接清单

交接给下一个人时，请确认对方拿到以下信息：

- [ ] GitHub 仓库地址和本项目目录位置。
- [ ] 本地 env 文件路径，以及每个 env key 应该填什么。
- [ ] Smartbi 报表名称、筛选条件和导出格式。
- [ ] 钉钉多维表格地址、字段名、视图或 sheet 信息。
- [ ] 测试群 chatid 和正式群 chatid 的 env key。
- [ ] 每个团队、小组、负责人、userid 和调度时间。
- [ ] Phase 2 Excel 表头行号和列名截图或说明。
- [ ] Phase 3 每个池子的列偏移 `column_offset` 来源。
- [ ] 本地试跑 phase1、phase2、phase3 的成功截图或日志。

## 上线前检查

- [ ] 配置范例不包含真实账号、密码、token。
- [ ] 配置范例不包含内部域名。
- [ ] 配置范例不包含真实姓名、手机号、学员信息。
- [ ] 本地 Excel、截图、日志、env 文件没有提交。
- [ ] `.gitignore` 已排除导出文件和临时文件。
- [ ] 在测试群跑通过 `phase1`、`phase2`、`phase3`。
- [ ] 确认图片和 Markdown 消息格式符合预期。
- [ ] 再切换正式群 chatid。

## 常见问题

### 配置文件找不到

确认命令中的 YAML 路径正确，并在项目目录下执行：

```bash
python engine.py examples/my_monitor.yaml 团队A phase2
```

### 凭证文件找不到

确认 `secrets_file` 指向的文件存在：

```bash
ls -la ~/.claude/secrets/intro_monitor.env
```

### BI 报表下载失败

检查：

1. `BI_URL/BI_USER/BI_PASS` 是否正确。
2. `BI_SKILL_DIR` 是否指向可用的 BI 自动化工具目录。
3. 报表名称是否与 Smartbi 中完全一致。
4. 日期筛选器 XPath 是否仍然有效。

### Excel 解析失败

检查：

1. `excel_parsing.header_rows` 是否是正确的 0-based 行号。
2. `excel_parsing.columns` 中的多级表头是否与 Excel 完全一致。
3. 报表导出格式是否变化。

### 钉钉消息发送失败

检查：

1. `DINGTALK_APP_KEY/DINGTALK_APP_SECRET` 是否正确。
2. `DINGTALK_ROBOT_CODE` 是否正确。
3. `teams.*.chatid_key` 对应的 env 变量是否存在。
4. 机器人是否已加入目标群聊。

## 文档

- [功能说明和架构](docs/architecture.md)
- [详细工作流程](docs/workflow.md)
- [完整配置范例](examples/weekly_intro_monitor.yaml)
- [HTML 模板](templates/dashboard.html)
