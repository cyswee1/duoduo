# 详细工作流程

## 总览

后端监控按“配置加载 → 数据拉取 → 数据处理 → 结果渲染 → 消息通知”的顺序执行。

```text
开始
  ↓
读取 YAML 配置
  ↓
加载本地凭证 env
  ↓
校验团队和阶段
  ↓
初始化数据源与通知器
  ↓
按 phase 类型执行对应流程
  ↓
生成文本 / 图片 / HTML 结果
  ↓
推送通知或保存文件
  ↓
结束
```

## Step 1：读取配置

执行命令：

```bash
python engine.py examples/weekly_intro_monitor.yaml 团队A phase2
```

引擎读取三个输入：

1. 配置文件路径：`examples/weekly_intro_monitor.yaml`
2. 团队名：`团队A`
3. 阶段名：`phase2`

配置加载器会读取：

- `name`：监控任务名称。
- `secrets_file`：凭证文件路径。
- `teams`：团队配置。
- `datasources`：数据源配置。
- `phases`：阶段配置。
- `notifier`：通知配置。
- `globals`：全局参数。

## Step 2：加载凭证

`secrets_file` 指向本地 env 文件，例如：

```yaml
secrets_file: ~/.claude/secrets/intro_monitor.env
```

该文件保存真实账号和密钥：

```bash
BI_URL=https://your-bi-host.example.com/smartbi/vision/index.jsp
BI_USER=your_bi_user
BI_PASS=your_bi_password
DINGTALK_APP_KEY=your_app_key
DINGTALK_APP_SECRET=your_app_secret
```

YAML 中只写环境变量名，不写真实值。

## Step 3：校验团队和阶段

引擎会检查：

- 团队名是否存在于 `teams`。
- 阶段名是否存在于 `phases`。
- 团队是否配置了该阶段的调度时间。
- 通知群 env key 是否能在凭证中找到。

如果任一项缺失，流程应停止并输出错误信息。

## Step 4：初始化数据源

### Smartbi 数据源

配置示例：

```yaml
datasources:
  smartbi:
    url_key: BI_URL
    user_key: BI_USER
    pass_key: BI_PASS
    reports:
      progress:
        name: "示例进度报表"
        output_filename: "progress.xlsx"
```

执行时会：

1. 从凭证中读取 `BI_URL/BI_USER/BI_PASS`。
2. 打开 BI 系统并登录。
3. 搜索或打开指定报表。
4. 应用日期筛选条件。
5. 下载 Excel 到 `globals.output_dir`。

### Notable 数据源

配置示例：

```yaml
datasources:
  notable:
    base_id_key: DINGTALK_TABLE_ID
    sheet_id_key: DINGTALK_TABLE_SHEET
    fields:
      group_name: "小组"
      progress_target: "进度目标"
```

执行时会：

1. 从凭证中读取表格 ID 和 sheet ID。
2. 请求多维表格数据。
3. 按字段映射提取目标、池子、小组等信息。

## Step 5：执行监控阶段

### Phase 1：目标登记提醒

适用场景：每天或每周开始前，提醒负责人登记目标。

流程：

1. 从多维表格读取各小组目标登记情况。
2. 对照团队 `tl_map` 找出未登记负责人。
3. 使用 `message_template` 填充：
   - `{team}`
   - `{unregistered_tls}`
   - `{deadline}`
   - `{table_url}`
4. 发送 Markdown 提醒到配置的群。

输出：提醒消息。

### Phase 2：进度监控

适用场景：监控当日进度、月度进度和目标缺口。

流程：

1. 下载 BI 进度报表。
2. 读取多维表格中的今日目标和月度目标。
3. 按 `excel_parsing.header_rows` 解析 Excel 多级表头。
4. 按 `excel_parsing.columns` 抽取字段。
5. 计算：
   - 今日达标率。
   - 月度完成率。
   - 当前 GAP。
6. 按 `thresholds.progress` 判断是否达标。
7. 用 `table_render` 配置生成表格图片。
8. 推送图片和摘要消息。

输出：进度表格图片和消息。

### Phase 3：跟进预警

适用场景：监控不同池子的外呼或跟进完成情况。

流程：

1. 下载 BI 跟进报表。
2. 遍历 `pool_configs` 中的池子。
3. 根据 `column_offset` 定位每个池子的字段段落。
4. 计算实际跟进率。
5. 与 `target` 和 `thresholds` 对比。
6. 筛出未达标行。
7. 渲染预警表格。
8. 推送到对应群。

输出：预警表格图片和消息。

## Step 6：结果渲染

当前支持表格图片渲染：

```yaml
table_render:
  title_template: "【监控标题 — {team}团队】"
  headers: [小组, TL, 今日目标, 今日完成, 达标率]
  color_rules:
    - column_index: 4
      condition: "< 0.8"
      color: red
```

渲染器根据配置生成可推送图片。`templates/dashboard.html` 提供 HTML 展示模板，可用于后续把监控结果保存为静态网页。

## Step 7：消息通知

通知器读取：

```yaml
notifier:
  type: dingtalk_robot
  robot_code_key: DINGTALK_ROBOT_CODE
  app_key: DINGTALK_APP_KEY
  app_secret_key: DINGTALK_APP_SECRET
```

发送目标由团队配置决定：

```yaml
teams:
  团队A:
    chatid_key: DINGTALK_TEST_CHATID
```

流程：

1. 读取 app key、app secret 和 robot code。
2. 获取 access token。
3. 根据 chatid 发送文本、Markdown 或图片。

## Step 8：本地输出与排查

常用本地输出：

- BI 下载 Excel：`globals.output_dir`
- 渲染图片：`globals.output_dir`
- 调试截图：本地下载目录或临时目录

排查顺序：

1. 配置文件是否能正常加载。
2. env 凭证是否存在且 key 名一致。
3. BI 报表名称是否正确。
4. Excel 表头行和字段映射是否匹配。
5. 通知群 chatid 是否配置。
6. 机器人是否有目标群权限。

## 上线前检查清单

- [ ] 配置范例不包含真实账号、密码、token。
- [ ] 配置范例不包含内部域名。
- [ ] 配置范例不包含真实姓名、手机号、学员信息。
- [ ] 本地 Excel、截图和日志未提交。
- [ ] `.gitignore` 已排除 env、导出文件和临时文件。
- [ ] 用测试群先跑通 phase1、phase2、phase3。
- [ ] 确认输出图片和消息格式符合预期。
