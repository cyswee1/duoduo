---
name: bi_skill
description: 在 BI 系统（Smartbi）中搜索/导航报表并下载，支持新旧两版导出和多种筛选方式。也可对已下载的 Excel 表格进行简单处理（筛选、排序、汇总等）。
user-invocable: true
allowed-tools:
  - Bash(python3 *)
  - Bash(pip3 install *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Write
---

# BI 技能

在 Smartbi BI 系统中自动化搜索或目录树导航打开报表、应用筛选并导出为 Excel，以及对下载后的表格进行处理。

## 使用方式

用户通过 `/bi_skill` 调用，按以下流程操作。

## 前置准备

**先检测**依赖是否已安装，**缺失才装**，不要每次都跑 pip install：

```bash
python3 -c "import playwright; import pandas; import openpyxl" 2>&1 || pip3 install playwright pandas openpyxl
```

Chromium 浏览器同理，已安装则跳过：

```bash
python3 -m playwright install chromium 2>&1
```

> 注意：`playwright install chromium` 只需执行一次，重复执行会在后台下载大量文件。检测到已有 chromium 就不要再装了。

脚本路径：`.claude/skills/bi_skill/bi_skill.py`

## 功能 1：从 BI 系统下载报表

### 参数解析

从用户输入中提取：
- **报表名称**（`--name`）：在 BI 系统中搜索报表名称
- **目录树路径**（`--path`）：通过目录树逐层导航到报表，如 `业务线\部门\报表名`
- **筛选条件**（`--filters`）：格式为 `列名=值` 或 `列名:值`，多个条件用逗号分隔
- **日期范围**（`--start-date` / `--end-date`）：格式 YYYY-MM-DD
- **多选筛选**（`--ms-filter` / `--ms-options`）：下拉多选筛选器名和选项
- **输出目录**（`--output`）：下载目录，默认 `~/Downloads`

> `--name` 和 `--path` 二选一即可。`--path` 适用于报表名称在树中不唯一或搜索难以定位的场景。优先使用 `--path`，搜索方式可能因 UI 元素拦截而双击失败。

### 执行命令

```bash
# 搜索方式
python3 .claude/skills/bi_skill/bi_skill.py search \
  --name "<报表名称>" \
  --filters "<列名>=<值>,<列名2>=<值2>" \
  --output "<输出目录>"

# 目录树路径方式（推荐）
python3 .claude/skills/bi_skill/bi_skill.py search \
  --path "业务线\\部门\\报表名" \
  --start-date "2025-01-01" \
  --end-date "2025-06-30"

# 带多选筛选
python3 .claude/skills/bi_skill/bi_skill.py search \
  --name "报表名" \
  --ms-filter "渠道一级分类" \
  --ms-options "投放,转介绍"
```

### 脚本行为

1. 打开 Chromium 浏览器，导航至 BI 系统
2. 自动登录（凭证从环境变量 `BI_USERNAME` / `BI_PASSWORD` 读取）
3. 点击左侧【分析展现】
4. 打开报表（二选一）：
   - **搜索方式**：搜索框输入 → JS dispatchEvent 双击结果打开（绕过 UI 拦截）
   - **目录树方式**：逐层 **双击文件夹名** 展开（Smartbi 树双击即可展开，无需找小箭头），最后双击报表名打开
5. 检查报表数据（检测"共 X 行"，无数据则自动刷新；播报类报表可能检测不到行数，不影响导出）
6. 依次应用筛选条件：
   - **列筛选**（combobox）：通过 `aliasSpan` 定位列名 → 点击 combobox-button → 选择选项
   - **日期筛选**：通过 JS 直接设置 input 值（`nativeInputValueSetter` + 触发 change 事件），无需操作日历组件
   - **多选筛选**：通过 `aliasSpan` 定位 → `span.closest('tr')` 找到 combobox-button → 点击弹出下拉 → 用 `page.mouse.click` 坐标点击选项 → 点击确定
7. **统一导出流程**：点击「导出」→ 找到「Excel」或「EXCEL」→ 点击「在线导出」
   - 新版报表优先 hover Excel 触发子菜单，找不到再 click
   - 在线导出使用 Playwright `getByText` / `locator` 定位，重试 3 次
8. 等待下载完成，输出文件路径（Playwright 下载事件 + fallback 文件扫描）

## 功能 2：处理已下载的 Excel 表格

### 执行命令

```bash
python3 .claude/skills/bi_skill/bi_skill.py process \
  --input "<Excel文件路径>" \
  --action "<操作类型>" \
  --params "<参数>"
```

支持的操作：
| 操作 | 说明 | params 示例 |
|------|------|-------------|
| `info` | 表格基本信息（行数、列名） | 无 |
| `head` | 查看前 N 行 | `10` |
| `columns` | 选取指定列 | `姓名,日期,金额` |
| `filter` | 按列值筛选行 | `校区=北京` |
| `sort` | 按列排序 | `金额,desc` |
| `summary` | 按列分组汇总 | `校区,金额,sum` |

## 关键实现细节

- **目录树导航**：Smartbi 树节点双击即可展开，使用 JS `dispatchEvent(new MouseEvent('dblclick', ...))` 绕过 Playwright 可点击检测
- **搜索双击**：搜索方式优先用 JS dblclick 事件，Playwright 原生双击容易因 splitter/icon 等 UI 元素拦截而超时
- **日期筛选**：通过 JS 直接设置 input 值并触发 `input`/`change`/`blur` 事件（`nativeInputValueSetter`）。Smartbi 的日期选择器是交互式日历组件（datepicker），两个日期输入框共享同一个 datepicker 实例，用日历点击方式容易串联，因此改用 JS 直接赋值
  - 定位方式：精确匹配 `span.aliasSpan` 文本（如"末次渠道时间开始"），找到标签右侧同行最近的 `input[type="text"]`
- **多选下拉筛选**：
  - 定位方式：`span.aliasSpan` 精确匹配筛选器名 → `span.closest('tr')` → TR 内的 `input.combobox-button`
  - 点击 combobox-button 弹出下拉列表
  - 选项是 `div.dropdown-box-span` 元素，必须用 `page.mouse.click(x, y)` 坐标点击（JS `element.click()` 对 Smartbi 复选框不生效）
  - 点击后等待，再点击「确定」按钮提交
- **导出流程**：统一为「导出 → Excel/EXCEL → 在线导出」三步，先 hover 后 click，兼容新旧两版
- **在线导出定位**：使用 Playwright `getByText("在线导出", exact=True)` 定位器 + `locator("text=在线导出")` + JS 查找三重 fallback，重试 3 次
- **下载等待**：优先等待 Playwright 下载事件（180s 超时），超时后扫描输出目录找最新 xlsx 文件
- **登录超时检测**：操作过程中如果弹出"登录超时"弹窗，自动刷新页面并重新登录
- Smartbi 是 SPA 架构，所有操作需等待元素加载
- 登录页面可能有验证码，如果出现验证码则提示用户手动介入
