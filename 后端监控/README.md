# 后端监控

后端监控是一个配置驱动的业务监控项目模板，用于把 BI 报表、多维表格目标、数据处理、表格渲染和通知推送串成一条自动化监控链路。

## 目录结构

```text
后端监控/
├── README.md                         # 使用指南
├── config_loader.py                  # YAML 配置加载与凭证加载
├── engine.py                         # 核心调度引擎
├── requirements.txt                  # Python 依赖
├── datasources/                      # 数据源模块
│   ├── smartbi.py                    # Smartbi 报表下载
│   └── notable.py                    # 多维表格读取
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

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 准备凭证

创建 `~/.claude/secrets/intro_monitor.env`：

```bash
# BI 系统
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_bi_user
BI_PASS=your_bi_password
BI_SKILL_DIR=/path/to/bi_skill

# 钉钉机器人
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

### 3. 修改配置

复制完整配置范例：

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

### 4. 运行监控

```bash
# 目标登记提醒
python engine.py examples/my_monitor.yaml 团队A phase1

# 进度监控
python engine.py examples/my_monitor.yaml 团队A phase2

# 跟进预警
python engine.py examples/my_monitor.yaml 团队A phase3
```

参数说明：

1. `examples/my_monitor.yaml`：配置文件路径。
2. `团队A`：配置中 `teams` 下定义的团队名。
3. `phase1/phase2/phase3`：配置中 `phases` 下定义的阶段名。

## 功能说明

### Phase 1：目标登记提醒

读取多维表格中的目标登记情况，识别未登记目标的负责人，并向指定群发送提醒消息。

### Phase 2：进度监控

下载 BI 进度报表，结合多维表格中的目标值，计算今日达标率、月度进度和缺口，并渲染成表格图片推送。

### Phase 3：跟进预警

下载 BI 跟进报表，根据不同池子的目标跟进率和阈值，识别未达标项并发送预警。

## 配置化原则

项目把原本容易硬编码的内容全部放到 YAML 或环境变量中：

| 内容 | 配置位置 |
| --- | --- |
| 团队和小组 | `teams` |
| 负责人和 userid | `teams.*.tl_map` |
| BI 地址和账号 | `secrets_file` 中的环境变量 |
| BI 报表名称 | `datasources.smartbi.reports.*.name` |
| Excel 表头和字段 | `phases.*.excel_parsing` |
| 达标阈值 | `phases.*.thresholds` |
| 池子名称和列偏移 | `phases.phase3.pool_configs` |
| 通知群 | `teams.*.chatid_key` |
| 表格样式 | `phases.*.table_render` |

## 文档

- [功能说明和架构](docs/architecture.md)
- [详细工作流程](docs/workflow.md)
- [完整配置范例](examples/weekly_intro_monitor.yaml)
- [HTML 模板](templates/dashboard.html)
