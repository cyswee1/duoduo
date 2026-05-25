# 功能说明和架构

## 项目目标

后端监控项目用于把分散在 BI 系统、多维表格和通知工具中的监控动作配置化，形成一套可复用的自动化链路：

1. 从配置文件读取团队、报表、字段、阈值和通知规则。
2. 从 BI 或多维表格拉取数据。
3. 按阶段执行数据处理。
4. 将结果渲染为文本、图片或 HTML。
5. 推送到指定群聊或输出到本地文件。

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

## 核心模块

### config_loader.py

负责加载 YAML 配置和凭证文件：

- 读取 `secrets_file` 指向的 env 文件。
- 将配置与环境变量解耦。
- 为引擎提供统一的配置对象。

### engine.py

核心调度入口：

- 解析命令行参数：配置文件、团队名、阶段名。
- 初始化数据源、处理器、渲染器和通知器。
- 根据 `phases.*.type` 分派到对应流程。

### datasources/smartbi.py

BI 报表数据源：

- 读取 BI 地址、账号和密码。
- 根据配置打开指定报表。
- 支持日期筛选和等待参数。
- 将报表下载为 Excel。

### datasources/notable.py

多维表格数据源：

- 读取目标登记表。
- 获取团队、小组、目标值、池子配置等业务输入。
- 为 phase1、phase2、phase3 提供目标侧数据。

### processors/progress.py

进度监控处理器：

- 解析多级表头 Excel。
- 按团队/小组汇总今日完成、月度完成和目标。
- 计算达标率、月进度和 GAP。

### processors/followup.py

跟进预警处理器：

- 按池子配置读取不同列段。
- 计算实际跟进率和目标差距。
- 输出未达标预警行。

### renderers/table_image.py

表格图片渲染器：

- 根据 `table_render.headers` 生成表格。
- 根据 `color_rules` 对重点单元格标色。
- 输出可被通知器发送的图片文件。

### notifiers/dingtalk.py

钉钉通知器：

- 获取 access token。
- 按 chatid 发送文本、Markdown 或图片消息。
- 支持通过配置控制目标群。

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

### datasources

配置所有外部数据源，例如 BI 报表、多维表格、未来可扩展的数据库或 API。

### phases

配置每个监控阶段的业务类型、输入数据源、字段映射、阈值、渲染规则和消息模板。

### notifier

配置通知渠道。当前示例使用钉钉机器人，也可以扩展到企业微信、飞书、邮件等渠道。

### globals

放置输出目录、全局池子、默认参数等多个阶段共用的配置。

## 扩展方式

### 增加新数据源

1. 在 `datasources/` 下新增模块。
2. 实现读取方法。
3. 在 `engine.py` 中按配置注册。
4. 在 YAML 的 `datasources` 中新增配置块。

### 增加新监控阶段

1. 在 `processors/` 下新增处理器。
2. 在 `engine.py` 中增加 `phase_type` 分支。
3. 在 YAML 的 `phases` 中定义新阶段。

### 增加新通知渠道

1. 在 `notifiers/` 下新增通知器。
2. 读取配置中的凭证 key。
3. 在 `notifier.type` 中切换渠道。

## 安全设计

- 真实凭证只放在本地 env 文件，不提交到仓库。
- 配置范例只保留占位符、示例团队和示例 ID。
- 本地下载的 Excel、截图、日志和导出文件应加入 `.gitignore`。
- 上传公开仓库前必须扫描 token、密码、内部域名、真实姓名、真实业务数据和个人路径。
