# Shoutui-Update 使用指南

## 快速开始

### 1. 安装依赖

```bash
pip3 install pandas openpyxl pyyaml playwright
playwright install chromium
```

### 2. 准备凭证

创建 `~/.claude/secrets/shoutui.env`:

```bash
export NETLIFY_TOKEN=your_netlify_token
export NETLIFY_SITE_ID=your_site_id
export NETLIFY_URL=https://your-site.netlify.app
```

设置权限:
```bash
chmod 600 ~/.claude/secrets/shoutui.env
```

### 3. 运行

```bash
cd <skill-dir>/shoutui-update
source ~/.claude/secrets/shoutui.env
python3 update.py examples/shoutui_link.yaml
```

## 执行模式

### 全自动(BI 下载 + 生成 + 部署)

```bash
python3 update.py examples/shoutui_link.yaml
```

### 已有 Excel,跳过 BI 下载

```bash
python3 update.py examples/shoutui_link.yaml --excel ~/Desktop/xxx.xlsx
```

### 只生成本地 HTML,不部署

```bash
python3 update.py examples/shoutui_link.yaml --excel ~/Desktop/xxx.xlsx --skip-deploy
```

### 部署但跳过测试

```bash
python3 update.py examples/shoutui_link.yaml --skip-test
```

### 指定输出目录

```bash
python3 update.py examples/shoutui_link.yaml --output-dir /tmp/test
```

## 配置文件说明

所有业务参数通过 YAML 配置注入。详见 `examples/shoutui_link.yaml`。

### 配置结构总览

```yaml
datasource:       # 数据源(BI 报表名、过滤条件、bi_skill 路径)
parsing:          # Excel 解析规则(表头定位、主键字段、有效行正则)
fields:           # 字段映射(BI 列名 → 输出字段名、TSV 字段顺序)
link_rules:       # 链接生成规则(按哪个字段分流、各分支的 PID)
html:             # HTML 生成(模板路径、压缩级别、占位符注入值)
deploy:           # Netlify 部署(token / site_id / public_url)
output:           # 输出配置(目录、是否保存处理后的 Excel)
```

### 各块详解

#### datasource — 数据源

```yaml
datasource:
  bi_skill_path: "../bi_skill/bi_skill.py"   # bi_skill 脚本路径(相对 update.py)
  report_name: "你的报表名称"                  # BI 中的报表名
  filters: "筛选条件=值"                       # 传给 bi_skill 的 --filters 参数
  timeout: 600                                # 下载超时(秒)
```

#### parsing — Excel 解析

```yaml
parsing:
  header_marker: "主键列名"       # 通过这个列名定位表头行(扫前 N 行)
  sid_field: "主键列名"           # 主键字段(必须在 column_map 的 key 中)
  sid_pattern: '^\d+$'           # 有效主键的正则(不匹配的行被过滤)
  max_header_scan_rows: 20       # 最多扫前多少行找表头
```

#### fields — 字段映射

```yaml
fields:
  column_map:                    # BI 原始列名 → 输出字段名
    BI列名A: field_a
    BI列名B: field_b
  tsv_fields: [field_a, field_b] # 内嵌到 HTML 的 TSV 字段顺序
  tsv_separator: "|"             # TSV 分隔符
```

#### link_rules — 链接生成规则

```yaml
link_rules:
  region_field: field_name       # 用哪个输出字段做分流判断
  uid_field: BI列名              # uid 对应的 BI 原始列名
  branches:                      # 分流分支(可多个)
    - match: "匹配值"            # 当 region_field == 此值时
      pid: "12345"               # 使用此 PID
      label: "显示标签"
  default:                       # 不匹配任何 branch 时的默认
    pid: "67890"
```

#### html — HTML 生成

```yaml
html:
  template_path: "template.html"  # 模板文件路径(相对 update.py)
  compress_level: 9               # gzip 压缩级别 0-9
  placeholders:                   # 注入到模板的占位符
    region_taiwan_value: "匹配值" # {{REGION_FIELD_VALUE_TAIWAN}}
    taiwan_pid: "12345"           # {{TAIWAN_PID}}
    default_pid: "67890"          # {{DEFAULT_PID}}
    link_base_template: "https://your-domain.com/path-{pid}?uid={uid}"  # {{LINK_BASE_TEMPLATE}}
```

#### deploy — Netlify 部署

```yaml
deploy:
  token: "${NETLIFY_TOKEN}"       # 从环境变量读取
  site_id: "${NETLIFY_SITE_ID}"
  public_url: "${NETLIFY_URL}"    # 部署后测试用的对外 URL
```

#### output — 输出

```yaml
output:
  output_dir: "~/Desktop"         # HTML 和 Excel 输出目录
  save_processed_excel: true      # 是否额外保存带链接列的 Excel
  processed_filename: "xxx.xlsx"  # 保存的文件名
```

### 环境变量引用

配置中 `${VAR_NAME}` 格式的值会在加载时自动替换为对应环境变量。适合放凭证类信息,避免明文写入配置文件。

## 创建新场景

### 步骤 1:复制范例

```bash
cp examples/shoutui_link.yaml examples/my_case.yaml
```

### 步骤 2:修改配置

按你的业务需求改:

1. `datasource.report_name` → 你要拉的 BI 报表名
2. `datasource.filters` → 报表筛选条件
3. `fields.column_map` → 你要抽取的 Excel 列
4. `fields.tsv_fields` → 内嵌到 HTML 的字段顺序
5. `link_rules` → 你的链接分流逻辑
6. `html.placeholders.link_base_template` → 你的链接模板

### 步骤 3:运行

```bash
python3 update.py examples/my_case.yaml
```

## 模板占位符

`template.html` 中使用以下占位符,运行时由配置注入:

| 占位符 | 来源 | 说明 |
|---|---|---|
| `{{B64_DATA}}` | 自动生成 | gzip + base64 后的 TSV 数据 |
| `{{REGION_FIELD_VALUE_TAIWAN}}` | `html.placeholders.region_taiwan_value` | 分流判断的字段值 |
| `{{TAIWAN_PID}}` | `html.placeholders.taiwan_pid` | 分流匹配时的 PID |
| `{{DEFAULT_PID}}` | `html.placeholders.default_pid` | 默认 PID |
| `{{LINK_BASE_TEMPLATE}}` | `html.placeholders.link_base_template` | 含 `{pid}` `{uid}` 的链接模板 |

## 故障排查

### BI 下载失败

- 检查 `bi_skill_path` 是否指向正确的 `bi_skill.py`
- 检查 BI 凭证是否已配置(bi_skill 自己读环境变量 `BI_URL/BI_USERNAME/BI_PASSWORD`)
- 检查报表名是否与 BI 系统中完全一致

### Excel 解析失败

- 检查 `header_marker` 是否与 Excel 中的列名完全一致
- 检查 `column_map` 中的列名是否存在于 Excel 表头
- 用 pandas 手动验证:

```python
import pandas as pd
df = pd.read_excel("xxx.xlsx", header=None, dtype=str)
for i in range(20):
    print(i, [v for v in df.iloc[i].tolist() if str(v) != 'nan'][:5])
```

### Netlify 部署失败

- 检查环境变量是否已 source: `echo $NETLIFY_TOKEN`
- 检查 token 是否过期(去 Netlify 后台确认)
- 检查 site_id 是否正确

### 链接测试失败

- CDN 缓存需要 1-2 分钟生效,可以加 `--skip-test` 先跳过,稍后手动验证
- 检查 `link_base_template` 中的域名是否可达

## 文档

- [SKILL.md](SKILL.md) — 功能说明和架构
- [examples/shoutui_link.yaml](examples/shoutui_link.yaml) — 完整配置范例
- [template.html](template.html) — HTML 模板(含占位符)
