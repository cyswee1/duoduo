---
name: shoutui-update
description: 配置驱动的链接生成 + Netlify 部署 — 从 BI 拉数据,按规则生成链接,内嵌到 HTML 部署到 Netlify
user-invocable: true
allowed-tools:
  - Bash(python3 *)
  - Bash(pip3 install *)
  - Bash(curl *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Bash(rm *)
  - Bash(cd *)
  - Bash(open *)
  - Read
  - Write
  - Edit
---

# Link-Update Skill(配置驱动)

通用流程: BI 下载 → Excel 解析 → 链接生成 → 自包含 HTML 构建 → Netlify 部署 → 测试。

业务参数(报表名、列映射、链接规则、Netlify 凭证)都通过 YAML 配置注入,不在代码里硬编码。

## 触发方式

- 手推链接周一例行更新: 直接调 `examples/shoutui_link.yaml`
- 新场景: 复制 `examples/shoutui_link.yaml` 改一改就能跑

## 执行命令

```bash
# 全自动(BI 下载 + 生成 + 部署)
python3 update.py examples/shoutui_link.yaml

# 已有 Excel,跳过 BI
python3 update.py examples/shoutui_link.yaml --excel ~/Desktop/xxx.xlsx

# 只生成本地 HTML 不部署
python3 update.py examples/shoutui_link.yaml --excel xxx.xlsx --skip-deploy

# 部署但不跑测试
python3 update.py examples/shoutui_link.yaml --skip-test

# 临时改输出目录
python3 update.py examples/shoutui_link.yaml --output-dir /tmp/test
```

## 凭证注入

Netlify 凭证从环境变量读取(避免写进配置文件被提交):

```bash
export NETLIFY_TOKEN=nfp_xxxx
export NETLIFY_SITE_ID=xxx-xxx-xxx
export NETLIFY_URL=https://your-site.netlify.app
```

或写入 `~/.claude/secrets/shoutui.env` 后 `source` 加载。

## 配置文件结构

详见 [examples/shoutui_link.yaml](examples/shoutui_link.yaml),包含 6 个顶层块:

| 块 | 用途 |
|---|---|
| `datasource` | BI 报表名 / 过滤条件 / 调用 bi_skill 的路径 |
| `parsing` | 表头定位规则、主键字段、有效行正则 |
| `fields.column_map` | BI 列名 → 输出字段名(决定 Excel 抽取范围) |
| `fields.tsv_fields` | 内嵌到 HTML 的 TSV 字段顺序 |
| `link_rules` | 按某个字段分流到不同 popularizeId 的规则 |
| `html.placeholders` | 注入到 template.html 的具体值(链接模板/PID/分流值) |
| `deploy` | Netlify token / site_id / public_url(都从环境变量取) |
| `output` | 输出目录 / 是否保存处理后的 Excel |

## 模板占位符

`template.html` 中保留以下占位符,运行时被 `placeholders` 注入:

- `{{B64_DATA}}` — gzip+base64 后的 TSV 数据
- `{{REGION_FIELD_VALUE_TAIWAN}}` — 用于分流判断的字段值
- `{{TAIWAN_PID}}` / `{{DEFAULT_PID}}` — 分流后的 popularizeId
- `{{LINK_BASE_TEMPLATE}}` — 含 `{pid}` `{uid}` 的链接模板

## 添加新场景

1. `cp examples/shoutui_link.yaml examples/my_case.yaml`
2. 改 `datasource.report_name` 为你要拉的报表
3. 改 `fields.column_map` 为你要抽的列
4. 改 `link_rules` 为你的分流逻辑(没有分流就只留 `default`)
5. 改 `html.placeholders.link_base_template` 为你的链接模板
6. 跑: `python3 update.py examples/my_case.yaml`

## 前置条件

```bash
pip3 install pandas openpyxl pyyaml playwright
playwright install chromium
```

## 实现要点

- BI 下载复用 `../bi_skill/bi_skill.py`(子进程方式),登录超时自动重试
- Excel 表头自动定位(扫前 N 行找 `header_marker` 列名)
- TSV 内嵌到 HTML,gzip level 9 + base64,浏览器端用 `DecompressionStream` 解压
- Netlify 部署用其 REST API,zip 上传单个 `index.html` + `netlify.toml`
- CDN 缓存 1-2 分钟生效
- 部署后测试: HEAD 请求验证 Content-Type + 抽样测试一条推广链接可达性
