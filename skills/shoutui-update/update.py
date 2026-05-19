#!/usr/bin/env python3
"""手推链接更新 — 一键完成 BI 下载 → 链接生成 → 部署 → 测试"""

import argparse
import base64
import gzip
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from io import BytesIO

import pandas as pd

# ── 默认配置 ──────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SKILL_DIR / "template.html"
BI_TOOL_PATH = SKILL_DIR.parent / "bi_skill" / "bi_skill.py"
# Netlify 凭证 — 从环境变量读取,不要硬编码
DEFAULT_NETLIFY_TOKEN = os.environ.get("NETLIFY_TOKEN", "")
NETLIFY_SITE_ID = os.environ.get("NETLIFY_SITE_ID", "")
NETLIFY_URL = os.environ.get("NETLIFY_URL", "")

# BI 报表配置 — 报表名通过环境变量注入
REPORT_NAME = os.environ.get("BI_REPORT_STUDENT_DETAIL", "")
DEFAULT_FILTERS = "是否在读学员=全部"
DEFAULT_OUTPUT_DIR = str(Path.home() / "Desktop")

# Excel 列名映射 (BI 原始列名 → 输出字段)
COLUMN_MAP = {
    "数学学生id": "sid",
    "平台用户ID": "uid",
    "微信昵称": "nick",
    "lp姓名": "lp",
    "lp组别": "group",
    "学员姓名": "student",
    "区域等级": "region",
}

# 手推链接配置
TAIWAN_PID = os.environ.get("TAIWAN_PID", "")
DEFAULT_PID = os.environ.get("DEFAULT_PID", "")
LINK_TEMPLATE = os.environ.get("LINK_TEMPLATE", "{pid}-{uid}")  # 推广链接模板,含 {pid}/{uid} 占位

# TSV 字段顺序 (与 template.html 中 JavaScript 解析顺序一致)
TSV_FIELDS = ["sid", "uid", "nick", "student", "lp", "group", "region"]


# ── 步骤 1：从 BI 下载 Excel ──────────────────────────────────

def download_excel(output_dir=None):
    """调用 bi_tool.py 从 Smartbi 下载报表，返回下载的文件路径"""
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    cmd = [
        sys.executable, str(BI_TOOL_PATH), "search",
        "--name", REPORT_NAME,
        "--filters", DEFAULT_FILTERS,
        "--output", str(output_dir),
    ]

    print(f"[1/4] 从 BI 下载报表...")
    print(f"  命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        print(f"[ERROR] BI 下载失败 (exit={result.returncode})")
        print(f"  stdout: {result.stdout[-500:]}")
        print(f"  stderr: {result.stderr[-500:]}")
        sys.exit(1)

    # 解析输出获取文件路径
    stdout = result.stdout
    filepath = None

    # 尝试从输出中匹配 "✅ 下载完成: <path>"
    match = re.search(r"下载完成[：:]\s*(.+\.xlsx?)", stdout)
    if match:
        filepath = match.group(1).strip()
        if Path(filepath).exists():
            print(f"  ✓ 下载完成: {filepath}")
            return filepath

    # Fallback: 在输出目录找最新的 Excel
    print("  → 从输出中未解析到路径，查找最新 Excel...")
    latest = _find_latest_excel(output_dir)
    if latest:
        print(f"  ✓ 找到: {latest}")
        return latest

    print("[ERROR] 未能找到下载的 Excel 文件")
    sys.exit(1)


# ── 步骤 2：处理 Excel 生成手推链接 ─────────────────────────────

def process_excel(excel_path):
    """读取 BI Excel，生成 TSV 数据和统计信息"""
    print(f"[2/4] 处理 Excel: {excel_path}")

    # 动态寻找表头行 (包含 '数学学生id' 的行)
    df_raw = pd.read_excel(excel_path, header=None, dtype=str)

    header_row = None
    for i in range(min(20, len(df_raw))):
        row_vals = [str(v).strip() for v in df_raw.iloc[i].tolist() if str(v) != "nan"]
        if "数学学生id" in row_vals:
            header_row = i
            break

    if header_row is None:
        print("[ERROR] 未在 Excel 中找到表头行（含'数学学生id'）")
        sys.exit(1)

    print(f"  表头行: 第 {header_row} 行 (0-indexed)")

    # 重新读取，跳过前面的说明行
    df = pd.read_excel(excel_path, header=header_row, dtype=str)
    print(f"  原始行数: {len(df)}")

    # 规范化列名（去除空格）
    df.columns = [str(c).strip() for c in df.columns]

    # 检查必需列是否存在
    missing = [c for c in COLUMN_MAP if c not in df.columns]
    if missing:
        print(f"[ERROR] 缺少必需列: {missing}")
        print(f"  实际列名: {list(df.columns)[:20]}")
        sys.exit(1)

    # 筛选有效数据（数学学生id 不为空且为纯数字）
    sid_col = "数学学生id"
    df = df[df[sid_col].notna() & df[sid_col].str.match(r"^\d+$")].copy()
    print(f"  有效行数: {len(df)}")

    # 提取并重命名列
    data = df[list(COLUMN_MAP.keys())].copy()
    data.columns = [COLUMN_MAP[c] for c in data.columns]

    # 填充空值
    for col in TSV_FIELDS:
        if col in data.columns:
            data[col] = data[col].fillna("").astype(str)

    # 生成 TSV
    tsv_lines = []
    for _, row in data.iterrows():
        vals = [row.get(f, "") for f in TSV_FIELDS]
        # 清洗：移除字段内的换行和管道符
        vals = [v.replace("\n", " ").replace("\r", "").replace("|", "/") for v in vals]
        tsv_lines.append("|".join(vals))

    tsv_text = "\n".join(tsv_lines)
    print(f"  TSV 大小: {len(tsv_text):,} 字符, {len(tsv_lines):,} 行")

    # 统计
    taiwan_count = sum(1 for _, r in data.iterrows() if r.get("region") == "台湾")
    print(f"  台湾学员: {taiwan_count:,} (popularizeId={TAIWAN_PID})")
    print(f"  非台湾学员: {len(data) - taiwan_count:,} (popularizeId={DEFAULT_PID})")

    return tsv_text, len(data)


# ── 步骤 3：生成部署 HTML ─────────────────────────────────────

def generate_html(tsv_text):
    """压缩 TSV 数据并填充 HTML 模板"""
    print(f"[3/4] 生成部署页面...")

    if not TEMPLATE_PATH.exists():
        print(f"[ERROR] 模板文件不存在: {TEMPLATE_PATH}")
        sys.exit(1)

    # Gzip 压缩
    tsv_bytes = tsv_text.encode("utf-8")
    compressed = gzip.compress(tsv_bytes, compresslevel=9)
    b64_data = base64.b64encode(compressed).decode("ascii")

    print(f"  原始: {len(tsv_bytes):,} bytes")
    print(f"  压缩后: {len(compressed):,} bytes (gzip level 9)")
    print(f"  Base64: {len(b64_data):,} chars")

    # 读取模板并替换
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "{{B64_DATA}}" not in template:
        print("[ERROR] 模板中缺少 {{B64_DATA}} 占位符")
        sys.exit(1)

    html = template.replace("{{B64_DATA}}", b64_data)

    # 写入输出文件
    output_path = Path(DEFAULT_OUTPUT_DIR) / "index.html"
    output_path.write_text(html, encoding="utf-8")
    output_size = output_path.stat().st_size
    print(f"  ✓ 页面已生成: {output_path} ({output_size:,} bytes)")

    return output_path


# ── 步骤 4：部署到 Netlify ────────────────────────────────────

def deploy_netlify(html_path, token, site_id=None):
    """将 HTML 页面部署到 Netlify"""
    if site_id is None:
        site_id = NETLIFY_SITE_ID

    print(f"[4/4] 部署到 Netlify (site: {site_id})...")

    # 创建临时部署目录
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 复制 index.html
        import shutil
        shutil.copy(html_path, tmp / "index.html")

        # 写入 netlify.toml
        netlify_toml = tmp / "netlify.toml"
        netlify_toml.write_text("""\
[[headers]]
  for = "/*"
  [headers.values]
    Content-Type = "text/html; charset=UTF-8"
""")

        # 创建 zip
        zip_path = tmp / "deploy.zip"
        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp / "index.html", "index.html")
            zf.write(netlify_toml, "netlify.toml")

        zip_size = zip_path.stat().st_size
        print(f"  部署包: {zip_size:,} bytes")

        # 上传到 Netlify
        import urllib.request
        import urllib.error

        url = f"https://api.netlify.com/api/v1/sites/{site_id}/deploys"
        data = zip_path.read_bytes()

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/zip")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            print(f"[ERROR] Netlify API 返回错误: {e.code}")
            print(f"  {e.read().decode()[:500]}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] 部署请求失败: {e}")
            sys.exit(1)

        state = result.get("state", "unknown")
        deploy_url = result.get("deploy_ssl_url") or result.get("url", "")
        print(f"  状态: {state}")
        print(f"  部署 URL: {deploy_url}")

        if state not in ("ready", "uploaded", "processing"):
            print(f"[ERROR] 部署状态异常: {state}")
            sys.exit(1)

    return NETLIFY_URL


# ── 步骤 5：测试 ──────────────────────────────────────────────

def test_deployment(url):
    """验证部署是否成功"""
    print(f"\n  测试部署...")
    import urllib.request

    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "")
            print(f"  HTTP {resp.status}, Content-Type: {ct}")
            if "text/html" not in ct:
                print(f"  ⚠️  Content-Type 不是 text/html")
                return False

        # 测试链接目标可达性
        test_link = LINK_TEMPLATE.format(pid=DEFAULT_PID, uid="test")
        req2 = urllib.request.Request(test_link, method="HEAD")
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            print(f"  手推链接可达: HTTP {resp2.status}")

        print(f"  ✓ 测试通过: {url}")
        return True

    except Exception as e:
        print(f"  ⚠️  测试未完全通过: {e}")
        return False


# ── 辅助函数 ──────────────────────────────────────────────────

def _find_latest_excel(directory):
    """在目录中找最新的 Excel 文件"""
    d = Path(directory)
    excels = [f for f in d.iterdir()
              if f.is_file() and f.suffix.lower() in (".xlsx", ".xls")
              and not f.name.startswith("~$") and not f.name.startswith(".~")]  # 排除临时文件
    if not excels:
        return None
    return str(max(excels, key=lambda f: f.stat().st_mtime))


# ── 主入口 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="手推链接更新 — 一键完成 BI 下载 → 链接生成 → 部署 → 测试"
    )
    parser.add_argument(
        "--excel",
        help="已有 Excel 文件路径（提供此参数可跳过 BI 下载步骤）",
    )
    parser.add_argument(
        "--token",
        help="Netlify Personal Access Token（部署必需）",
    )
    parser.add_argument(
        "--site-id",
        default=NETLIFY_SITE_ID,
        help=f"Netlify Site ID (默认: {NETLIFY_SITE_ID})",
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="跳过部署，仅生成本地 index.html",
    )
    parser.add_argument(
        "--skip-test",
        action="store_true",
        help="跳过部署后测试",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Excel 和 HTML 输出目录 (默认: {DEFAULT_OUTPUT_DIR})",
    )

    args = parser.parse_args()

    start_time = time.time()

    # ── 步骤 1：获取 Excel ──
    if args.excel:
        excel_path = args.excel
        if not Path(excel_path).exists():
            print(f"[ERROR] 文件不存在: {excel_path}")
            sys.exit(1)
        print(f"[1/4] 使用已有 Excel: {excel_path}")
    else:
        excel_path = download_excel(args.output_dir)

    # ── 步骤 2：生成手推链接数据 ──
    tsv_text, record_count = process_excel(excel_path)

    # ── 步骤 3：生成部署页面 ──
    html_path = generate_html(tsv_text)

    elapsed = time.time() - start_time
    print(f"\n{'─' * 50}")
    print(f"数据统计:")
    print(f"  学员总数: {record_count:,}")
    print(f"  页面大小: {html_path.stat().st_size:,} bytes")
    print(f"  耗时: {elapsed:.0f}s")

    # ── 步骤 4：部署 ──
    token = args.token or DEFAULT_NETLIFY_TOKEN
    if args.skip_deploy:
        print(f"\n  跳过部署 (--skip-deploy)")
        print(f"  本地页面: {html_path}")
    else:
        deployed_url = deploy_netlify(html_path, token, args.site_id)
        deploy_elapsed = time.time() - start_time
        print(f"\n{'─' * 50}")
        print(f"部署完成!")
        print(f"  页面地址: {deployed_url}")
        print(f"  总耗时: {deploy_elapsed:.0f}s")

        # ── 步骤 5：测试 ──
        if not args.skip_test:
            # 给 Netlify CDN 一点时间
            time.sleep(3)
            test_deployment(deployed_url)

    # 保存处理后的 Excel（含手推链接列）供查阅
    _save_processed_excel(excel_path)


def _save_processed_excel(excel_path):
    """保存一份带手推链接列的 Excel 到桌面供查阅"""
    try:
        header_row = None
        df_raw = pd.read_excel(excel_path, header=None, dtype=str, nrows=20)
        for i in range(len(df_raw)):
            row_vals = [str(v).strip() for v in df_raw.iloc[i].tolist() if str(v) != "nan"]
            if "数学学生id" in row_vals:
                header_row = i
                break

        if header_row is None:
            return

        df = pd.read_excel(excel_path, header=header_row, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]

        sid_col = "数学学生id"
        if sid_col not in df.columns:
            return

        df = df[df[sid_col].notna() & df[sid_col].str.match(r"^\d+$")].copy()

        uid_col = "平台用户ID"
        region_col = "区域等级"

        if uid_col not in df.columns or region_col not in df.columns:
            return

        def _make_link(row):
            pid = TAIWAN_PID if str(row.get(region_col, "")) == "台湾" else DEFAULT_PID
            return LINK_TEMPLATE.format(pid=pid, uid=row[uid_col])

        df["手推链接"] = df.apply(_make_link, axis=1)

        # 只保留关键列
        keep_cols = [sid_col, uid_col, "微信昵称", "学员姓名", "lp姓名", "lp组别", region_col, "手推链接"]
        available = [c for c in keep_cols if c in df.columns]
        df_out = df[available].copy()

        # 重命名
        rename = {v: k for k, v in COLUMN_MAP.items()}
        df_out.rename(columns={rename.get(c, c): c for c in df_out.columns}, inplace=True)

        out_path = Path(DEFAULT_OUTPUT_DIR) / "手推链接_最新.xlsx"
        df_out.to_excel(out_path, index=False)
        print(f"  处理结果已保存: {out_path} ({len(df_out):,} 行)")
    except Exception as e:
        print(f"  ⚠️  保存处理结果失败: {e}")


if __name__ == "__main__":
    main()
