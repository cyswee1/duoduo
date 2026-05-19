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

一键自动化:从 BI 下载学员明细 → 生成手推链接 → 部署到 Netlify → 测试验证。

## 触发方式

用户说「更新手推链接」或调用 `/shoutui-update`。

## 完整流程

```text
1. 从 BI 下载学员明细 Excel
2. 解析 Excel,按区域规则生成手推链接
3. 构建自包含 HTML 查询页面(数据内嵌 + 浏览器端解压)
4. 部署到 Netlify
5. 测试部署可访问性
```

## 执行方式

```bash
# 全自动(BI 下载 + 生成 + 部署)
python3 update.py

# 已有 Excel,只做生成 + 部署
python3 update.py --excel <path>

# 仅生成本地页面,不部署
python3 update.py --excel <path> --skip-deploy
```

## 配置项

所有真实凭证通过环境变量注入,不在代码中硬编码:

- BI 凭证:`BI_URL` / `BI_USERNAME` / `BI_PASSWORD`
- Netlify:`NETLIFY_TOKEN` / `NETLIFY_SITE_ID` / `NETLIFY_URL`
- 链接生成规则、报表名、字段映射详见 `update.py` 顶部常量

## 前置条件

- `pip3 install pandas openpyxl playwright` 已安装
- Google Chrome 浏览器已安装
- Netlify Personal Access Token

## 实现要点

- BI 下载用 Playwright 自动化(复用 `bi_skill`),首次可能 3-5 分钟
- 数据采用 TSV + gzip + base64 内嵌到 HTML,浏览器端用 `DecompressionStream` 解压
- 登录超时自动重试 3 次,验证码场景需手动介入
- 部署后 CDN 缓存可能 1-2 分钟生效
