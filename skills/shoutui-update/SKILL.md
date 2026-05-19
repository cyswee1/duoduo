---
name: shoutui-update
description: 手推链接更新 — 一键完成「BI 下载 → 手推链接生成 → Netlify 部署 → 测试」全流程
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

# 手推链接更新 Skill

一键自动化：从 BI 下载「思维学员明细（学员维度）」→ 生成所有学员手推链接 → 部署到 Netlify → 测试验证。

## 触发方式

用户说「更新手推链接」或调用 `/shoutui-update`。

## 完整流程

### 方案 A：全自动（推荐，适合周一例行更新）

```bash
python3 .claude/skills/shoutui-update/update.py
```

这会自动完成：
1. 从 Smartbi BI 下载「思维学员明细（学员维度）」报表（筛选「是否在读学员=全部」）
2. 生成所有学员的手推链接（台湾 → popularizeId=71181，其他 → 4113）
3. 构建自包含 HTML 查询页面
4. 部署到 Netlify(站点 URL 从 `NETLIFY_URL` 环境变量读取)
5. 测试部署是否成功

### 方案 B：已有 Excel，只做更新

```bash
python3 .claude/skills/shoutui-update/update.py \
  --excel ~/Desktop/思维学员明细（学员维度）.xlsx
```

### 方案 C：仅生成本地页面（不部署）

```bash
python3 .claude/skills/shoutui-update/update.py \
  --excel ~/Desktop/思维学员明细（学员维度）.xlsx \
  --skip-deploy
```

## 前置条件

- `pip3 install pandas openpyxl playwright` 已安装
- Google Chrome 浏览器已安装
- Netlify Personal Access Token（用于部署）

## Netlify 部署信息

- **Site ID**: 通过环境变量 `NETLIFY_SITE_ID` 配置
- **Site URL**: 通过环境变量 `NETLIFY_URL` 配置
- **Token**: 通过环境变量 `NETLIFY_TOKEN` 配置（也可通过 `--token` / `--site-id` 命令行参数覆盖）

## 手推链接生成规则

- **台湾学员**（区域等级 = 台湾）：`popularizeId=71181`
- **非台湾学员**：`popularizeId=4113`

链接模板：
```
https://market-h5.61info.cn/maliang/popularize-{pid}.html?business_Type=invite&courseBelong=WANDOU&courseSubjectType=1&page_source=shoutui&popularizeId={pid}&invite_userID={uid}
```

## 数据格式

- BI 报表：`思维学员明细（学员维度）`，筛选 `是否在读学员=全部`
- 页面内嵌 TSV 格式（`|` 分隔）：`sid|uid|nick|student|lp|group|region`
- 压缩方式：gzip level 9 → base64，浏览器端用 `DecompressionStream` 解压

## 测试验证清单

部署完成后验证：
1. 页面 Content-Type 为 `text/html; charset=UTF-8`
2. 手推链接目标可访问（HTTP 200）
3. 页面可正常查询并展示学员信息

## 实现注意事项

- BI 下载可能需要 3-5 分钟（Smartbi 服务端处理 + Playwright 自动化）
- 登录超时会自动重试 3 次，若仍失败需手动介入或手动下载 Excel 后用方案 B
- 如果 BI 登录出现验证码，需手动介入
- 部署后 CDN 缓存可能需要 1-2 分钟生效
- 每周一执行一次即可更新当周新学员数据
- 处理结果会额外保存为 `~/Desktop/手推链接_最新.xlsx` 供查阅
