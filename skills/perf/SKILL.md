---
name: perf
description: 海外思维 LP/TL/LP经理/对接负责人/拓科 转介绍激励计算 — 一键下载 BI 源数据、生成业绩明细、计算全套激励
user-invocable: true
allowed-tools:
  - Bash(python3 *)
  - Bash(pip3 install *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Write
  - Edit
---

# 转介绍激励计算 Skill

从 BI 下载源数据 → 生成业绩明细 → 计算多角色激励,输出整合 Excel。

## 触发方式

用户说「计算激励」「跑激励」「更新激励」或调用 `/perf`。

## 完整流程

```text
1. 下载 BI 源数据(销售明细 / 业绩播报 / LP架构表)
2. 自动下载滚动成单(动态计算筛选日期)
3. 生成业绩明细(过滤团队范围、归属规则、滚动口径)
4. 按角色逐层计算激励:
   - LP 个人激励
   - TL 小组激励
   - LP 经理激励
   - 对接负责人激励
   - 拓科激励
5. 整合输出到 Excel(多 sheet)
```

## 执行命令

```bash
python3 perf.py --month <M> --year <Y> --base-dir <激励目录>
```

主要选项:
- `--month` / `--year`:计算月份(默认当月)
- `--base-dir`:数据文件夹
- `--skip-download`:跳过 BI 下载,使用已有源文件
- `--skip-incentive`:只生成业绩明细,不计算激励

## 配置项

所有真实凭证和业务参数通过环境变量注入,不在代码中硬编码:

- BI 凭证:`BI_URL` / `BI_USERNAME` / `BI_PASSWORD`
- 兼任 TL/LP 的特殊人员:`EXTRA_LP_NAMES`(逗号分隔)
- 具体激励档位、门槛、金额、奖金池规模:**不入仓**,由本地 `激励/` 目录下的方案文件维护

## 输出 Sheet 结构

| Sheet | 内容 |
|---|---|
| `业绩明细` | 逐行业绩(当月例子 / 重复进线 / 滚动成单) |
| `LP激励` | 按 LP 汇总的激励计算 |
| `TL业绩汇总` / `TL激励` | TL 维度业绩与激励 |
| `LP经理激励` | LP 经理激励 |
| `对接负责人激励` | 对接负责人激励 |
| `拓科激励` | 拓科相关激励 |

## 前置条件

```bash
python3 -c "import playwright; import pandas; import openpyxl" 2>&1 \
  || pip3 install playwright pandas openpyxl
```

## 实现要点

- 销售明细 header 在 row 7(0-indexed),数据从 row 8 起
- 业绩播报为多段结构(整体/团队/区域/小组/LP/主管),按段解析
- LP 筛选基于职位和在职状态,兼任 TL 的人员通过 `EXTRA_LP_NAMES` 补入
- 团队过滤排除非目标团队
- 当月入职判断:入职时间 ≥ 当月 1 日
