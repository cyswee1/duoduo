#!/usr/bin/env python3
"""配置驱动的链接生成 + Netlify 部署 skill

流程: BI 下载 → Excel 解析 → 链接生成 → 自包含 HTML 构建 → Netlify 部署 → 测试

所有业务参数(数据源、列映射、链接规则、Netlify 凭证)由 YAML 配置注入。
"""

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

import pandas as pd
import yaml


SKILL_DIR = Path(__file__).resolve().parent


# ── 配置加载 ──────────────────────────────────────────────────

def load_config(config_path):
    """加载 YAML 配置,展开 ${env_var} 形式的环境变量引用"""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    def _expand(obj):
        if isinstance(obj, str):
            m = re.fullmatch(r"\$\{([A-Z_][A-Z0-9_]*)\}", obj)
            if m:
                return os.environ.get(m.group(1), "")
            return re.sub(
                r"\$\{([A-Z_][A-Z0-9_]*)\}",
                lambda x: os.environ.get(x.group(1), ""),
                obj,
            )
        if isinstance(obj, dict):
            return {k: _expand(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_expand(v) for v in obj]
        return obj

    return _expand(cfg)


def _resolve_path(p, base):
    """把相对路径解析为绝对路径(相对于 base)"""
    if not p:
        return None
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return p
    return str((Path(base) / p).resolve())


# ── 步骤 1:从 BI 下载 Excel ──────────────────────────────────

def download_excel(cfg, output_dir):
    """通过 bi_skill 子进程下载 BI 报表"""
    ds = cfg["datasource"]
    bi_tool = _resolve_path(ds["bi_skill_path"], SKILL_DIR)
    if not bi_tool or not Path(bi_tool).exists():
        print(f"[ERROR] bi_skill 不存在: {bi_tool}")
        sys.exit(1)

    cmd = [
        sys.executable, bi_tool, "search",
        "--name", ds["report_name"],
        "--filters", ds.get("filters", ""),
        "--output", str(output_dir),
    ]
    print(f"[1/4] 从 BI 下载报表 {ds['report_name']!r} ...")
    print(f"  命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=ds.get("timeout", 600))

    if result.returncode != 0:
        print(f"[ERROR] BI 下载失败 (exit={result.returncode})")
        print(f"  stdout: {result.stdout[-500:]}")
        print(f"  stderr: {result.stderr[-500:]}")
        sys.exit(1)

    match = re.search(r"下载完成[：:]\s*(.+\.xlsx?)", result.stdout)
    if match and Path(match.group(1).strip()).exists():
        path = match.group(1).strip()
        print(f"  ✓ 下载完成: {path}")
        return path

    latest = _find_latest_excel(output_dir)
    if latest:
        print(f"  ✓ 找到最新 Excel: {latest}")
        return latest

    print("[ERROR] 未能找到下载的 Excel 文件")
    sys.exit(1)


# ── 步骤 2:解析 Excel,生成 TSV ──────────────────────────────

def process_excel(cfg, excel_path):
    """读取 BI Excel,按列映射抽取字段,生成 TSV 数据流"""
    print(f"[2/4] 处理 Excel: {excel_path}")

    parsing = cfg["parsing"]
    column_map = cfg["fields"]["column_map"]
    tsv_fields = cfg["fields"]["tsv_fields"]
    header_marker = parsing["header_marker"]
    sid_field = parsing["sid_field"]
    sid_pattern = parsing.get("sid_pattern", r"^\d+$")

    df_raw = pd.read_excel(excel_path, header=None, dtype=str)
    header_row = None
    for i in range(min(parsing.get("max_header_scan_rows", 20), len(df_raw))):
        row_vals = [str(v).strip() for v in df_raw.iloc[i].tolist() if str(v) != "nan"]
        if header_marker in row_vals:
            header_row = i
            break

    if header_row is None:
        print(f"[ERROR] 未在 Excel 中找到表头行(含 {header_marker!r})")
        sys.exit(1)
    print(f"  表头行: 第 {header_row} 行 (0-indexed)")

    df = pd.read_excel(excel_path, header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    print(f"  原始行数: {len(df)}")

    missing = [c for c in column_map if c not in df.columns]
    if missing:
        print(f"[ERROR] 缺少必需列: {missing}")
        print(f"  实际列名: {list(df.columns)[:20]}")
        sys.exit(1)

    df = df[df[sid_field].notna() & df[sid_field].str.match(sid_pattern)].copy()
    print(f"  有效行数: {len(df)}")

    data = df[list(column_map.keys())].copy()
    data.columns = [column_map[c] for c in data.columns]
    for col in tsv_fields:
        if col in data.columns:
            data[col] = data[col].fillna("").astype(str)

    sep = cfg["fields"].get("tsv_separator", "|")
    tsv_lines = []
    for _, row in data.iterrows():
        vals = [row.get(f, "") for f in tsv_fields]
        vals = [v.replace("\n", " ").replace("\r", "").replace(sep, "/") for v in vals]
        tsv_lines.append(sep.join(vals))

    tsv_text = "\n".join(tsv_lines)
    print(f"  TSV 大小: {len(tsv_text):,} 字符, {len(tsv_lines):,} 行")

    _print_link_stats(cfg, data)
    return tsv_text, len(data), data


def _print_link_stats(cfg, data):
    """按 link_rules 打印各分组的记录数"""
    rules = cfg.get("link_rules", {})
    region_field = rules.get("region_field")
    if not region_field or region_field not in data.columns:
        return
    branches = rules.get("branches", [])
    for b in branches:
        if "match" in b:
            n = sum(1 for _, r in data.iterrows() if r.get(region_field) == b["match"])
            print(f"  {b.get('label', b['match'])}: {n:,} (popularizeId={b['pid']})")
    default = rules.get("default", {})
    if default:
        all_matches = set(b["match"] for b in branches if "match" in b)
        n = sum(1 for _, r in data.iterrows() if r.get(region_field) not in all_matches)
        print(f"  其他: {n:,} (popularizeId={default.get('pid')})")


# ── 步骤 3:生成自包含 HTML ───────────────────────────────────

def generate_html(cfg, tsv_text, output_dir):
    """gzip 压缩 TSV → base64 → 注入到 HTML 模板"""
    print(f"[3/4] 生成部署页面...")

    template_path = _resolve_path(cfg["html"]["template_path"], SKILL_DIR)
    if not Path(template_path).exists():
        print(f"[ERROR] 模板文件不存在: {template_path}")
        sys.exit(1)

    tsv_bytes = tsv_text.encode("utf-8")
    compressed = gzip.compress(tsv_bytes, compresslevel=cfg["html"].get("compress_level", 9))
    b64_data = base64.b64encode(compressed).decode("ascii")
    print(f"  原始: {len(tsv_bytes):,} bytes")
    print(f"  压缩后: {len(compressed):,} bytes")
    print(f"  Base64: {len(b64_data):,} chars")

    template = Path(template_path).read_text(encoding="utf-8")
    placeholders = cfg["html"].get("placeholders", {})

    substitutions = {
        "{{B64_DATA}}": b64_data,
        "{{REGION_FIELD_VALUE_TAIWAN}}": placeholders.get("region_taiwan_value", ""),
        "{{TAIWAN_PID}}": str(placeholders.get("taiwan_pid", "")),
        "{{DEFAULT_PID}}": str(placeholders.get("default_pid", "")),
        "{{LINK_BASE_TEMPLATE}}": placeholders.get("link_base_template", ""),
    }
    html = template
    for k, v in substitutions.items():
        html = html.replace(k, v)

    if "{{B64_DATA}}" in html:
        print("[ERROR] 模板替换后仍有 {{B64_DATA}},检查模板")
        sys.exit(1)

    output_path = Path(output_dir) / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"  ✓ 页面已生成: {output_path} ({output_path.stat().st_size:,} bytes)")
    return output_path


# ── 步骤 4:Netlify 部署 ──────────────────────────────────────

def deploy_netlify(cfg, html_path):
    """打包 HTML 上传到 Netlify"""
    nl = cfg["deploy"]
    token = nl.get("token")
    site_id = nl.get("site_id")
    if not token or not site_id:
        print("[ERROR] deploy.token / deploy.site_id 未配置(可通过环境变量注入)")
        sys.exit(1)

    print(f"[4/4] 部署到 Netlify (site: {site_id}) ...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        import shutil
        shutil.copy(html_path, tmp / "index.html")

        netlify_toml = tmp / "netlify.toml"
        netlify_toml.write_text(nl.get("netlify_toml", '[[headers]]\n  for = "/*"\n  [headers.values]\n    Content-Type = "text/html; charset=UTF-8"\n'))

        zip_path = tmp / "deploy.zip"
        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp / "index.html", "index.html")
            zf.write(netlify_toml, "netlify.toml")

        print(f"  部署包: {zip_path.stat().st_size:,} bytes")

        import urllib.request, urllib.error
        url = f"https://api.netlify.com/api/v1/sites/{site_id}/deploys"
        req = urllib.request.Request(url, data=zip_path.read_bytes(), method="POST")
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

    return nl.get("public_url") or deploy_url


# ── 步骤 5:部署后测试 ────────────────────────────────────────

def test_deployment(cfg, url):
    print(f"\n  测试部署: {url}")
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "")
            print(f"  HTTP {resp.status}, Content-Type: {ct}")
            if "text/html" not in ct:
                print(f"  ⚠️  Content-Type 不是 text/html")
                return False

        rules = cfg.get("link_rules", {})
        default = rules.get("default", {})
        link_template = cfg["html"].get("placeholders", {}).get("link_base_template", "")
        if link_template and default.get("pid"):
            test_link = link_template.replace("{pid}", str(default["pid"])).replace("{uid}", "test")
            with urllib.request.urlopen(urllib.request.Request(test_link, method="HEAD"), timeout=15) as resp2:
                print(f"  推广链接可达: HTTP {resp2.status}")

        print(f"  ✓ 测试通过")
        return True
    except Exception as e:
        print(f"  ⚠️  测试未完全通过: {e}")
        return False


# ── 辅助:保存处理后的 Excel 供查阅 ───────────────────────────

def save_processed_excel(cfg, data, output_dir):
    out_cfg = cfg.get("output", {})
    if not out_cfg.get("save_processed_excel"):
        return
    rules = cfg.get("link_rules", {})
    region_field = rules.get("region_field")
    uid_field_label = cfg["fields"]["column_map"].get(rules.get("uid_field"), "uid")
    link_template = cfg["html"].get("placeholders", {}).get("link_base_template", "")

    def _make_link(row):
        pid = rules.get("default", {}).get("pid", "")
        for b in rules.get("branches", []):
            if row.get(region_field) == b.get("match"):
                pid = b["pid"]
                break
        return link_template.replace("{pid}", str(pid)).replace("{uid}", str(row.get(uid_field_label, "")))

    df_out = data.copy()
    df_out["link"] = df_out.apply(_make_link, axis=1)

    out_name = out_cfg.get("processed_filename", "processed.xlsx")
    out_path = Path(output_dir) / out_name
    df_out.to_excel(out_path, index=False)
    print(f"  处理结果已保存: {out_path} ({len(df_out):,} 行)")


def _find_latest_excel(directory):
    d = Path(directory)
    excels = [
        f for f in d.iterdir()
        if f.is_file() and f.suffix.lower() in (".xlsx", ".xls")
        and not f.name.startswith("~$") and not f.name.startswith(".~")
    ]
    return str(max(excels, key=lambda f: f.stat().st_mtime)) if excels else None


# ── 主入口 ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="配置驱动的链接生成 + Netlify 部署 skill"
    )
    parser.add_argument("config", help="YAML 配置文件路径")
    parser.add_argument("--excel", help="跳过 BI 下载,使用已有 Excel")
    parser.add_argument("--skip-deploy", action="store_true", help="跳过 Netlify 部署")
    parser.add_argument("--skip-test", action="store_true", help="跳过部署后测试")
    parser.add_argument("--output-dir", help="覆盖配置中的 output_dir")
    args = parser.parse_args()

    cfg = load_config(args.config)
    output_dir = args.output_dir or cfg.get("output", {}).get("output_dir") or str(Path.home() / "Desktop")
    output_dir = os.path.expanduser(output_dir)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    start = time.time()

    if args.excel:
        excel_path = os.path.expanduser(args.excel)
        if not Path(excel_path).exists():
            print(f"[ERROR] 文件不存在: {excel_path}")
            sys.exit(1)
        print(f"[1/4] 使用已有 Excel: {excel_path}")
    else:
        excel_path = download_excel(cfg, output_dir)

    tsv_text, count, data = process_excel(cfg, excel_path)
    html_path = generate_html(cfg, tsv_text, output_dir)

    print(f"\n{'─'*50}")
    print(f"数据统计:")
    print(f"  记录数: {count:,}")
    print(f"  页面大小: {html_path.stat().st_size:,} bytes")
    print(f"  耗时: {time.time()-start:.0f}s")

    if args.skip_deploy:
        print(f"\n  跳过部署 (--skip-deploy)")
        print(f"  本地页面: {html_path}")
    else:
        deployed_url = deploy_netlify(cfg, html_path)
        print(f"\n{'─'*50}")
        print(f"部署完成!")
        print(f"  页面地址: {deployed_url}")
        print(f"  总耗时: {time.time()-start:.0f}s")
        if not args.skip_test:
            time.sleep(3)
            test_deployment(cfg, deployed_url)

    save_processed_excel(cfg, data, output_dir)


if __name__ == "__main__":
    main()
