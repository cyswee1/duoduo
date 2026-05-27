# 详细工作流程

本文说明后端监控从“读取配置”到“发送通知”的完整执行链路。新人接手时，建议先读 [README.md](../README.md)，再按本文理解每个阶段内部做了什么。

## 总览

后端监控按“配置加载 → 凭证读取 → 数据拉取 → 数据处理 → 结果渲染 → 消息通知”的顺序执行。所有团队、报表、字段、阈值和通知群都来自 YAML 配置或本地 env 凭证文件。

```text
开始
  ↓
读取 YAML 配置
  ↓
加载本地凭证 env
  ↓
校验团队和阶段
  ↓
初始化 Smartbi / Notable / 通知器
  ↓
按 phase 类型执行对应流程
  ↓
生成文本或表格图片
  ↓
推送到配置的群
  ↓
结束
```

## 入口命令

```bash
python engine.py examples/weekly_intro_monitor.yaml 团队A phase2
```

三个参数分别是：

1. 配置文件路径：例如 `examples/weekly_intro_monitor.yaml`。
2. 团队名：必须存在于 YAML 的 `teams` 中。
3. 阶段名：必须存在于 YAML 的 `phases` 中。

推荐新人先复制配置范例再试跑：

```bash
cp examples/weekly_intro_monitor.yaml examples/my_monitor.yaml
python engine.py examples/my_monitor.yaml 团队A phase1
python engine.py examples/my_monitor.yaml 团队A phase2
python engine.py examples/my_monitor.yaml 团队A phase3
```

## Step 1：加载配置

`config_loader.py` 负责读取 YAML，并解析全局参数、团队配置、数据源配置、阶段配置和通知器配置。

关键配置块：

| 配置块 | 作用 | 新人需要确认 |
| --- | --- | --- |
| `secrets_file` | 指向本地 env 凭证文件 | 文件存在且权限正确 |
| `teams` | 团队、小组、负责人、调度时间、通知群 env key | 小组名和负责人名单准确 |
| `datasources` | Smartbi 和多维表格数据源参数 | 报表名、表格字段、筛选器准确 |
| `phases` | 每个阶段的类型、字段映射、阈值、渲染规则 | 表头、列偏移、阈值准确 |
| `notifier` | 通知渠道和凭证 env key | 机器人凭证和群 ID 可用 |
| `globals` | 输出目录和全局共享参数 | 输出目录可写 |

配置加载时会解析模板变量：

- `{this_monday}`：本周一日期，格式 `YYYY-MM-DD`。
- `{today}`：当天日期，格式 `YYYY-MM-DD`。

这些变量可用于 Smartbi 日期筛选条件。

## Step 2：加载凭证

真实账号和密钥只放在本地 env 文件中，例如：

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

YAML 中只保存这些变量名，不保存真实值。公开仓库里只能提交示例变量名和占位值。

检查方式：

```bash
ls -la ~/.claude/secrets/intro_monitor.env
chmod 600 ~/.claude/secrets/intro_monitor.env
```

## Step 3：初始化组件

`engine.py` 会初始化三个核心对象：

1. `SmartbiDataSource`：负责调用 BI 自动化能力下载报表。
2. `NotableDataSource`：负责读取多维表格里的目标登记、目标值和池子配置。
3. `DingTalkNotifier`：负责发送 Markdown 消息或图片消息。

初始化依赖两个前提：

- YAML 中的数据源配置完整。
- env 文件中的 key 与 YAML 中的 `*_key` 字段能对上。

## Step 4：校验团队和阶段

执行前要确认：

- 命令中的团队名存在于 `teams`。
- 命令中的阶段名存在于 `phases`。
- 团队的 `chatid_key` 能在 env 文件中找到。
- 当前阶段需要的数据源已经配置。

如果缺失，先改配置，不要改代码。

## Step 5：按阶段执行

### Phase 1：目标登记提醒

适用场景：提醒负责人在截止时间前登记目标。

配置入口：

```yaml
phases:
  phase1:
    type: registration_reminder
    datasource: notable
    message_template: |
      ### {team} 目标登记提醒
      **未登记负责人**：{unregistered_tls}
      请在 {deadline} 前完成登记：
      [点击打开目标登记表]({table_url})
```

执行流程：

1. 从多维表格读取当前团队的目标登记记录。
2. 根据 `teams.*.tl_map` 获取应登记的负责人名单。
3. 对比已登记小组，找出未登记负责人。
4. 用 `message_template` 填充 `{team}`、`{unregistered_tls}`、`{deadline}`、`{table_url}`。
5. 通过钉钉机器人发送 Markdown 提醒。

输出：目标登记提醒消息。

排查重点：

- `tl_map` 中负责人是否完整。
- 多维表格字段 `group_name` 是否与配置一致。
- `table_url_template` 是否能打开正确表格。

### Phase 2：进度监控

适用场景：监控今日完成、月度进度和目标缺口。

配置入口：

```yaml
phases:
  phase2:
    type: progress_monitor
    datasource: smartbi.progress
    notable_datasource: notable
    excel_parsing:
      header_rows: [3, 4]
      columns:
        team_group: ['团队/小组', '团队/小组']
        lp: ['成员', '成员']
        tl: ['负责人', '负责人']
        today_count: ['今日完成情况', '今日完成数']
        total_count: ['月度完成情况', '累计完成数']
    thresholds:
      progress: 0.8
```

执行流程：

1. 根据 `phases.phase2.datasource` 定位 Smartbi 报表配置。
2. 下载进度报表到 `globals.output_dir`。
3. 从多维表格读取每个小组的今日目标和月度进度目标。
4. 按 `excel_parsing.header_rows` 读取 Excel 多级表头。
5. 按 `excel_parsing.columns` 抽取小组、成员、负责人、今日完成、累计完成等字段。
6. 排除负责人行、总计行和空行，只汇总成员行。
7. 计算今日达标率、月度完成率、月目标和 GAP。
8. 用 `TableRenderer.render_progress_table()` 渲染表格图片。
9. 通过钉钉机器人推送图片。

输出：进度监控表格图片。

排查重点：

- `header_rows` 是 0-based 行号，不是 Excel 里肉眼看到的 1-based 行号。
- `columns` 中的多级表头必须和 Excel 完全一致。
- 小组名称必须能同时匹配 BI 报表和多维表格。
- 今日目标、月度进度目标必须能转成数字。

### Phase 3：跟进预警

适用场景：监控指定池子的跟进率是否低于目标。

配置入口：

```yaml
phases:
  phase3:
    type: pool_warning
    datasource: smartbi.followup
    pool_configs:
      - name: "池子A"
        column_offset: 22
        target: 0.5
    thresholds:
      call_low: 0.5
```

执行流程：

1. 根据 `phases.phase3.datasource` 下载跟进报表。
2. 从多维表格读取每个小组需要监控的池子列表。
3. 遍历 `pool_configs`，按 `column_offset` 从 Excel 中读取该池子的实际跟进率。
4. 与池子目标值 `target` 或默认阈值 `thresholds.call_low` 对比。
5. 生成未达标或无数据的预警项。
6. 如果没有预警项，流程结束且不发送消息。
7. 如果有预警项，用 `TableRenderer.render_followup_table()` 渲染图片。
8. 通过钉钉机器人推送图片。

输出：跟进预警表格图片。

排查重点：

- `pool_configs[].name` 必须和多维表格中的池子名称或 `pool_name_mapping` 映射后名称一致。
- `column_offset` 是从 Excel 第 0 列开始计算的列序号。
- 跟进率单元格必须能转成数字。

## Step 6：结果渲染

当前主要使用 `renderers/table_image.py` 生成图片表格。渲染规则来自 phase 配置：

```yaml
table_render:
  title_template: "【进度监控 — {team}】"
  headers: [小组, 负责人, 今日目标, 今日完成, 今日达标率, 月目标, 月完成, 月进度, GAP]
  color_rules:
    - column_index: 4
      condition: "< 0.8"
      color: red
```

`headers` 控制表头，`color_rules` 控制需要高亮的列和条件。`templates/dashboard.html` 是预留的 HTML 展示模板，适合后续把监控结果沉淀成静态页面。

## Step 7：消息通知

通知目标由团队配置决定：

```yaml
teams:
  团队A:
    chatid_key: DINGTALK_TEST_CHATID
```

通知凭证由通知器配置决定：

```yaml
notifier:
  type: dingtalk_robot
  robot_code_key: DINGTALK_ROBOT_CODE
  app_key: DINGTALK_APP_KEY
  app_secret_key: DINGTALK_APP_SECRET
```

执行时会从 env 中读取真实值，并发送到对应群。

建议上线前先用测试群：

1. `teams.*.chatid_key` 先指向测试群 env key。
2. 三个 phase 都跑通后，再切换正式群 env key。
3. 切换正式群后先跑低风险的 phase1，确认机器人权限正常。

## 配置化边界

以下内容应通过 YAML 或 env 注入，不应写死在代码里：

- 团队名、小组名、负责人和 userid。
- BI 地址、账号、密码、报表名称。
- Excel 表头行、字段名、列偏移。
- 多维表格 base id、sheet id、字段名。
- 阈值、目标池子、颜色规则。
- 钉钉机器人凭证和群聊 ID。

## 上线前检查清单

- [ ] 配置范例不包含真实账号、密码、token。
- [ ] 配置范例不包含内部域名。
- [ ] 配置范例不包含真实姓名、手机号、学员信息。
- [ ] 本地 Excel、截图、日志、env 文件没有提交。
- [ ] `.gitignore` 已排除导出文件和临时文件。
- [ ] 在测试群跑通过 `phase1`、`phase2`、`phase3`。
- [ ] 确认图片和 Markdown 消息格式符合预期。
- [ ] 切换正式群前复核 `chatid_key`。
