# Monitor Skill 工作流

## 总览

`monitor` skill 按“配置加载 → 凭证读取 → 数据拉取 → 数据处理 → 结果渲染 → 消息通知”的顺序执行。所有团队、报表、字段、阈值和通知群都来自 YAML 配置或本地 env 凭证文件。

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

## Step 1：加载配置

`config_loader.py` 负责读取 YAML，并解析全局参数、团队配置、数据源配置、阶段配置和通知器配置。

关键配置块：

| 配置块 | 作用 |
| --- | --- |
| `secrets_file` | 指向本地 env 凭证文件 |
| `teams` | 团队、小组、负责人、调度时间、通知群 env key |
| `datasources` | Smartbi 和多维表格数据源参数 |
| `phases` | 每个阶段的类型、字段映射、阈值、渲染规则 |
| `notifier` | 通知渠道和凭证 env key |
| `globals` | 输出目录和全局共享参数 |

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
DINGTALK_TEST_CHATID=your_chatid
```

YAML 中只保存这些变量名，不保存真实值。公开仓库里只能提交示例变量名和占位值。

## Step 3：初始化组件

`engine.py` 会初始化三个核心对象：

1. `SmartbiDataSource`：负责调用 BI 下载报表。
2. `NotableDataSource`：负责读取多维表格里的目标登记、目标值和池子配置。
3. `DingTalkNotifier`：负责发送 Markdown 消息或图片消息。

## Step 4：按阶段执行

### Phase 1：目标登记提醒

适用场景：提醒负责人在截止时间前登记目标。

流程：

1. 从多维表格读取当前团队的目标登记记录。
2. 根据 `teams.*.tl_map` 获取应登记的负责人名单。
3. 对比已登记小组，找出未登记负责人。
4. 用 `message_template` 填充 `{team}`、`{unregistered_tls}`、`{deadline}`、`{table_url}`。
5. 通过钉钉机器人发送 Markdown 提醒。

输出：目标登记提醒消息。

### Phase 2：进度监控

适用场景：监控今日完成、月度进度和目标缺口。

流程：

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

### Phase 3：跟进预警

适用场景：监控指定池子的跟进率是否低于目标。

流程：

1. 根据 `phases.phase3.datasource` 下载跟进报表。
2. 从多维表格读取每个小组需要监控的池子列表。
3. 遍历 `pool_configs`，按 `column_offset` 从 Excel 中读取该池子的实际跟进率。
4. 与池子目标值 `target` 或默认阈值 `thresholds.call_low` 对比。
5. 生成未达标或无数据的预警项。
6. 如果没有预警项，流程结束且不发送消息。
7. 如果有预警项，用 `TableRenderer.render_followup_table()` 渲染图片。
8. 通过钉钉机器人推送图片。

输出：跟进预警表格图片。

## Step 5：结果渲染

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

`headers` 控制表头，`color_rules` 控制需要高亮的列和条件。

## Step 6：消息通知

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
