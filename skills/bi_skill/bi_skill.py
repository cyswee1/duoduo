#!/usr/bin/env python3
"""BI 技能 — Smartbi 报表下载（搜索+目录树）+ 新旧版导出 + Excel 后处理."""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# ── 配置 ─────────────────────────────────────────────────────── BI 凭证从环境变量读取,不要硬编码
BI_URL = os.environ.get("BI_URL", "")
USERNAME = os.environ.get("BI_USERNAME", "")
PASSWORD = os.environ.get("BI_PASSWORD", "")


# ── CLI 参数 ────────────────────────────────────────────────────

def _make_search_parser():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--name", default="", help="报表名称（搜索方式）")
    p.add_argument("--path", default="", help="目录树路径（如: 业务线\\部门\\报表名）")
    p.add_argument("--filters", default="", help="列筛选，格式: 列名=值,列名2=值2")
    p.add_argument("--start-date", default="", help="开始日期 YYYY-MM-DD")
    p.add_argument("--end-date", default="", help="结束日期 YYYY-MM-DD")
    p.add_argument("--start-date-field", default="开始时间", help="开始日期筛选器字段名")
    p.add_argument("--end-date-field", default="结束时间", help="结束日期筛选器字段名")
    p.add_argument("--ms-filter", default="", help="多选筛选器名称")
    p.add_argument("--ms-options", default="", help="多选筛选选项，逗号分隔")
    p.add_argument("--output", default=str(Path.home() / "Downloads"), help="下载目录")
    return p


def _make_process_parser():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--input", required=True, help="Excel 文件路径")
    p.add_argument("--action", required=True,
                   choices=["filter", "sort", "summary", "columns", "head", "info"])
    p.add_argument("--params", default="", help="操作参数")
    return p


# ══════════════════════════════════════════════════════════════════
# search 子命令 — BI 报表搜索 / 导航 / 筛选 / 导出
# ══════════════════════════════════════════════════════════════════

def do_search(args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] 请先安装: pip3 install playwright")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    filters = _parse_filters(args.filters)
    ms_options = [o.strip() for o in args.ms_options.split(",") if o.strip()] if args.ms_options else []

    print(f"[搜索] name={args.name or '(目录树)'}")
    print(f"[路径] {args.path or '(搜索方式)'}")
    print(f"[筛选] {filters or '无'}")
    print(f"[日期] {args.start_date} ~ {args.end_date}" if args.start_date else "[日期] 无")
    print(f"[多选] {args.ms_filter}={ms_options}" if ms_options else "[多选] 无")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ── 1. 登录 ──
        print("[1/7] 登录...")
        _login(page)

        # ── 2. 进入分析展现 ──
        print("[2/7] 进入「分析展现」...")
        page.locator("span[bofid='Analysis']").first.click()
        time.sleep(3)
        print("  ✓ 已进入")

        # ── 3. 打开报表（搜索 or 目录树） ──
        print("[3/7] 打开报表...")
        if args.path:
            report_name = _open_by_path(page, args.path)
        elif args.name:
            report_name = _open_by_search(page, args.name)
        else:
            print("[ERROR] 请指定 --name 或 --path")
            browser.close()
            sys.exit(1)
        print(f"  ✓ 报表已打开: {report_name}")

        # ── 4. 应用筛选（刷新之前） ──
        print("[4/7] 应用筛选条件...")
        _diagnose_filters(page)
        if filters:
            _apply_filters(page, filters)
        if args.start_date:
            _apply_date_filter_v2(page, args.start_date_field, args.start_date)
        if args.end_date:
            _apply_date_filter_v2(page, args.end_date_field, args.end_date)
        if args.ms_filter and ms_options:
            _apply_multiselect_filter(page, args.ms_filter, ms_options)
        if not filters and not args.start_date and not ms_options:
            print("  无筛选条件")

        # ── 5. 刷新数据 ──
        print("[5/7] 刷新数据...")
        _refresh_and_wait(page)

        # ── 6. 导出 ──
        print("[6/7] 导出报表...")
        _do_export(page)

        # ── 7. 等待下载 ──
        print("[7/7] 等待下载...")
        filepath = _wait_download(context, page, output_dir)
        if filepath:
            print(f"\n✅ 下载完成: {filepath}")
        else:
            print("\n❌ 下载失败")

        time.sleep(1)
        browser.close()
        return filepath


# ══════════════════════════════════════════════════════════════════
# process 子命令 — Excel 后处理
# ══════════════════════════════════════════════════════════════════

def do_process(args):
    import pandas as pd

    path = Path(args.input)
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}")
        sys.exit(1)

    df = pd.read_excel(path) if path.suffix in (".xlsx", ".xls") else pd.read_csv(path)
    action, params = args.action, args.params

    if action == "info":
        print(f"行数: {len(df)}")
        print(f"列数: {len(df.columns)}")
        print(f"列名: {list(df.columns)}")
        print(f"\n前 5 行预览:\n{df.head().to_string()}")
        return

    if action == "head":
        n = int(params) if params else 5
        print(df.head(n).to_string())
        return

    if action == "columns":
        cols = [c.strip() for c in params.split(",")] if params else []
        if cols:
            existing = [c for c in cols if c in df.columns]
            missing = [c for c in cols if c not in df.columns]
            if missing:
                print(f"⚠️  列不存在: {missing}")
            df = df[existing]
        print(df.to_string())
        return

    if action == "filter":
        col, val = _parse_kv(params)
        if col in df.columns:
            df = df[df[col].astype(str).str.contains(str(val), na=False)]
            print(f"筛选后行数: {len(df)}\n{df.to_string()}")
        else:
            print(f"[ERROR] 列不存在: {col}")
        return

    if action == "sort":
        parts = [p.strip() for p in params.split(",")]
        col, asc = parts[0], len(parts) < 2 or parts[1].lower() != "desc"
        if col in df.columns:
            df = df.sort_values(by=col, ascending=asc)
            print(df.to_string())
        else:
            print(f"[ERROR] 列不存在: {col}")
        return

    if action == "summary":
        parts = [p.strip() for p in params.split(",")]
        if len(parts) >= 3:
            gc, ac, m = parts[0], parts[1], parts[2]
            if gc in df.columns and ac in df.columns:
                print(df.groupby(gc)[ac].agg(m).to_string())
            else:
                print("[ERROR] 列不存在")
        else:
            print("[ERROR] 参数格式: 分组列,聚合列,sum|count|avg")
        return


# ─────────────────────────────────────────────────────────────────
# 登录
# ─────────────────────────────────────────────────────────────────

def _login(page, max_retries=3):
    for attempt in range(max_retries):
        try:
            page.goto(BI_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)
            page.locator("input.item-textinput").first.fill(USERNAME)
            page.locator("input.item-textinput").nth(1).fill(PASSWORD)
            page.locator("input.item-submit").click()
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(5)
            print("  ✓ 登录成功")
            return
        except Exception as e:
            print(f"  ⚠️ 登录超时 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print("  → 重试...")
                time.sleep(3)
    print("[ERROR] 登录失败，请手动介入")
    sys.exit(1)


def _check_session_timeout(page) -> bool:
    """检测是否弹出登录超时弹窗，如果是则刷新页面重新登录."""
    timeout_detected = page.evaluate('''
        () => {
            const all = document.querySelectorAll('*');
            for (const el of all) {
                const text = (el.textContent || '').trim();
                if (text.includes('登录超时') || text.includes('会话超时') || text.includes('session timeout') || text.includes('重新登录')) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.width < 600) {
                        return true;
                    }
                }
            }
            return false;
        }
    ''')
    if timeout_detected:
        print("  ⚠️ 检测到登录超时，刷新页面...")
        page.reload(wait_until="networkidle", timeout=30000)
        time.sleep(3)
        # 如果刷新后回到登录页，重新登录
        login_input = page.query_selector("input.item-textinput")
        if login_input:
            page.locator("input.item-textinput").first.fill(USERNAME)
            page.locator("input.item-textinput").nth(1).fill(PASSWORD)
            page.locator("input.item-submit").click()
            page.wait_for_load_state("networkidle")
            time.sleep(5)
            print("  ✓ 重新登录成功")
        return True
    return False


# ─────────────────────────────────────────────────────────────────
# 方式 A：搜索打开报表
# ─────────────────────────────────────────────────────────────────

def _open_by_search(page, name: str) -> str:
    print(f"  搜索: {name}")
    search_box = page.locator("div.base__task-tree-search-row input").first
    search_box.click()
    search_box.fill(name)
    search_box.press("Enter")
    time.sleep(5)

    # 双击搜索结果打开
    _dblclick_report(page, name)
    return name


def _dblclick_report(page, name: str):
    """双击搜索结果中的报表链接打开（优先 JS 事件，避免 UI 拦截）."""
    for attempt in range(2):
        # JS 直接触发 dblclick 事件（需要两次双击才能打开报表）
        js_ok = page.evaluate(f'''
            () => {{
                const all = document.querySelectorAll('a');
                for (const a of all) {{
                    if (a.textContent && a.textContent.trim() === '{name}') {{
                        a.dispatchEvent(new MouseEvent('dblclick', {{ bubbles: true, cancelable: true }}));
                        return true;
                    }}
                }}
                return false;
            }}
        ''')
        if js_ok:
            time.sleep(3 if attempt == 0 else 5)
            print(f"    ✓ 第 {attempt + 1} 次双击 (JS)")
            continue
        # fallback: Playwright 原生双击
        links = page.locator(f"a:has-text('{name}')")
        for i in range(links.count()):
            el = links.nth(i)
            if el.is_visible():
                try:
                    el.dblclick(timeout=5000)
                    time.sleep(3 if attempt == 0 else 5)
                    print(f"    ✓ 第 {attempt + 1} 次双击")
                    break
                except Exception:
                    continue

    page.wait_for_load_state("networkidle")
    time.sleep(5)


# ─────────────────────────────────────────────────────────────────
# 方式 B：目录树路径导航打开报表
# ─────────────────────────────────────────────────────────────────

def _open_by_path(page, path: str) -> str:
    """通过目录树路径逐层双击展开并打开报表."""
    parts = [p.strip() for p in path.replace("/", "\\").split("\\")]

    for i, name in enumerate(parts):
        is_last = (i == len(parts) - 1)
        action = "双击打开" if is_last else "双击展开"
        print(f"  {action}: {name}")

        # JS dispatchEvent dblclick 绕过 UI 拦截
        ok = page.evaluate(f'''
            () => {{
                const all = document.querySelectorAll('a');
                for (const a of all) {{
                    if (a.textContent.trim() === '{name}') {{
                        a.dispatchEvent(new MouseEvent('dblclick', {{ bubbles: true, cancelable: true }}));
                        return true;
                    }}
                }}
                return false;
            }}
        ''')
        if ok:
            time.sleep(3 if not is_last else 15)
            print(f"    ✓ {'报表已打开' if is_last else '已展开'} (JS)")
        else:
            print(f"    ⚠️ 未找到: {name}")

    return parts[-1]


# ─────────────────────────────────────────────────────────────────
# 数据检查 & 刷新
# ─────────────────────────────────────────────────────────────────

def _refresh_and_wait(page, max_wait=120):
    """点击刷新按钮，等待数据加载完成，检测「共X行」."""
    refresh = page.query_selector('input[title="刷新"]')
    if refresh:
        refresh.click()
    else:
        page.mouse.click(117, 88)
    print("  ✓ 已点击刷新")

    # 等待加载动画消失
    for i in range(max_wait):
        time.sleep(1)
        result = page.evaluate('''
            () => {
                // 检查是否有 loading 遮罩
                const loaders = document.querySelectorAll('[class*="loading"], [class*="Loading"]');
                for (const l of loaders) {
                    const r = l.getBoundingClientRect();
                    if (r.width > 50 && r.height > 50) return { loading: true };
                }
                // 检查「共X行」
                const spans = document.querySelectorAll('span');
                for (let i = 0; i < spans.length; i++) {
                    const text = spans[i].textContent;
                    if (text && text.indexOf('共') >= 0 && (text.indexOf('行') >= 0 || text.indexOf('条') >= 0)) {
                        const match = text.match(/共\\s*(\\d+)\\s*行/);
                        if (match && parseInt(match[1]) > 0) {
                            return { loading: false, count: parseInt(match[1]) };
                        }
                    }
                }
                return { loading: false, count: 0 };
            }
        ''')
        if result.get("loading"):
            if i % 10 == 0:
                print(f"  ... 加载中 ({i}s)")
            continue
        if result.get("count") and result["count"] > 0:
            print(f"  ✓ 数据已加载: 共 {result['count']} 行")
            return True, result["count"]
        # 数据没加载出来但也没 loading，可能是还没渲染完，再等几秒
        if i > 10:
            # 再等一轮看是否有数据
            continue

    print("  ⚠️ 刷新超时，未检测到行数")
    return False, 0


# ─────────────────────────────────────────────────────────────────
# 列筛选（combobox）
# ─────────────────────────────────────────────────────────────────

def _apply_filters(page, filters: dict):
    for col_name, value in filters.items():
        print(f"  → [{col_name}] = [{value}]")
        _set_filter(page, col_name, value)
        time.sleep(2)


def _set_filter(page, col_name: str, value: str):
    alias = page.locator(f"span.aliasSpan:has-text('{col_name}')").first
    if not alias.is_visible(timeout=5000):
        print(f"    ⚠️ 未找到筛选列: {col_name}")
        return

    tr = alias.locator("xpath=ancestor::tr[1]")
    btn = tr.locator("input.combobox-button").first
    if not btn.is_visible(timeout=3000):
        print(f"    ⚠️ 未找到筛选控件")
        return

    btn.click()
    time.sleep(1.5)

    opt = page.locator(f".dropdown-box-span:has-text('{value}')").first
    if opt.is_visible(timeout=2000):
        opt.click()
        time.sleep(1)
        print(f"    ✓ 已选择: {value}")
    else:
        for sel in [f"text='{value}'", f"div:has-text('{value}')", f"span:has-text('{value}')"]:
            try:
                el = page.locator(sel).last
                if el.is_visible(timeout=1000):
                    el.click()
                    time.sleep(1)
                    print(f"    ✓ 已选择: {value}")
                    _wait_refresh(page)
                    return
            except Exception:
                continue
        print(f"    ⚠️ 未找到选项: {value}")

    _wait_refresh(page)


# ─────────────────────────────────────────────────────────────────
# 筛选器 DOM 诊断
# ─────────────────────────────────────────────────────────────────

def _diagnose_filters(page):
    """探测报表筛选器区域的 DOM 结构，找出实际使用的元素."""
    info = page.evaluate('''
        () => {
            const result = {
                aliasSpan: [],
                inputs: [],
                labels: [],
            };
            // 1. 所有 aliasSpan
            document.querySelectorAll('span.aliasSpan').forEach(s => {
                const t = s.textContent.trim();
                if (t) {
                    const tr = s.closest('tr');
                    const hasInput = tr ? !!tr.querySelector('input') : false;
                    const hasCombobox = tr ? !!tr.querySelector('input.combobox-button') : false;
                    result.aliasSpan.push({text: t, hasInput, hasCombobox});
                }
            });
            // 2. 所有可见的 input[type="text"]（可能用于日期）
            document.querySelectorAll('input[type="text"]').forEach(inp => {
                const r = inp.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && r.width < 300) {
                    const v = inp.value || '';
                    // 找同行的标签文本
                    const tr = inp.closest('tr');
                    const labelSpan = tr ? (tr.querySelector('span.aliasSpan') || tr.querySelector('span')) : null;
                    const label = labelSpan ? labelSpan.textContent.trim() : '';
                    result.inputs.push({value: v, label, x: r.x, y: r.y, w: r.width, h: r.height});
                }
            });
            // 3. 查找带"时间"/"日期"/"开始"/"结束"关键词的可见文本
            document.querySelectorAll('span, div, label').forEach(el => {
                const t = (el.textContent || '').trim();
                if (t && (t.includes('时间') || t.includes('日期') || t.includes('开始') || t.includes('结束'))
                    && t.length < 30) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.width < 200) {
                        result.labels.push({text: t, tag: el.tagName, x: r.x, y: r.y});
                    }
                }
            });
            return result;
        }
    ''')
    print("  ── 筛选器诊断 ──")
    if info.get('aliasSpan'):
        for s in info['aliasSpan']:
            print(f"    aliasSpan: [{s['text']}] input={s['hasInput']} combobox={s['hasCombobox']}")
    else:
        print("    aliasSpan: 无")
    if info.get('inputs'):
        for s in info['inputs']:
            print(f"    input[type=text]: label=[{s['label']}] value=[{s['value']}] pos=({s['x']:.0f},{s['y']:.0f}) size={s['w']:.0f}x{s['h']:.0f}")
    if info.get('labels'):
        for s in info['labels']:
            print(f"    label: [{s['text']}] tag={s['tag']} pos=({s['x']:.0f},{s['y']:.0f})")
    else:
        print("    时间/日期相关标签: 无")

# ─────────────────────────────────────────────────────────────────
# 日期筛选
# ─────────────────────────────────────────────────────────────────

def _apply_date_filter_v2(page, field_name: str, date_value: str):
    """使用交互式日期选择器设置日期.

    流程:
    1. 精确定位日期输入框
    2. 点击输入框弹出日历
    3. 如果当前月份就是目标月份，直接选日期
    4. 否则：点击导航栏 → 点击年份 → 选年 → 选月 → 选日
    5. 点击空白处关闭日历
    """
    from datetime import datetime

    try:
        dt = datetime.strptime(date_value, "%Y-%m-%d")
        year, month, day = dt.year, dt.month, dt.day
        month_names = ["一月", "二月", "三月", "四月", "五月", "六月",
                       "七月", "八月", "九月", "十月", "十一月", "十二月"]
        month_name = month_names[month - 1]
    except ValueError:
        print(f"    ⚠️ 日期格式错误: {date_value}")
        return

    print(f"  设置 {field_name}: {date_value} ({year}年 {month_name} {day}日)")

    # JS 设置 input 值并触发事件
    # 定位方式：aliasSpan 匹配（先精确，后包含） → span.closest('tr') → TR 内的 input[type="text"]
    set_ok = page.evaluate(f'''
        () => {{
            const spans = document.querySelectorAll('span.aliasSpan');
            // 先精确匹配
            for (const span of spans) {{
                const t = span.textContent.trim();
                if (t === '{field_name}' || t === '{field_name}：' || t === '{field_name}:') {{
                    const tr = span.closest('tr');
                    if (tr) {{
                        const inp = tr.querySelector('input[type="text"]');
                        if (inp) {{
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(inp, '{date_value}');
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            return {{ found: true, matched: t, value: inp.value }};
                        }}
                    }}
                }}
            }}
            // 再包含匹配
            for (const span of spans) {{
                const t = span.textContent.trim();
                if (t.includes('{field_name}')) {{
                    const tr = span.closest('tr');
                    if (tr) {{
                        const inp = tr.querySelector('input[type="text"]');
                        if (inp) {{
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            nativeInputValueSetter.call(inp, '{date_value}');
                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            return {{ found: true, matched: t, value: inp.value }};
                        }}
                    }}
                }}
            }}
            // 未找到，列出所有可用字段名
            const allNames = [];
            for (const span of spans) {{
                const t = span.textContent.trim();
                if (t) {{
                    const tr = span.closest('tr');
                    if (tr && tr.querySelector('input[type="text"]')) {{
                        allNames.push(t);
                    }}
                }}
            }}
            return {{ found: false, available: allNames }};
        }}
    ''')

    if set_ok and set_ok.get('found'):
        print(f"    ✓ 匹配字段: [{set_ok.get('matched')}] 已设置值: {set_ok.get('value')}")
        time.sleep(1)
        print(f"  ✓ {field_name} 设置完成: {date_value}")
    else:
        available = set_ok.get('available', []) if set_ok else []
        if available:
            print(f"    ⚠️ 未找到日期输入框: {field_name}")
            print(f"    可用的日期字段: {available}")
        else:
            print(f"    ⚠️ 未找到任何 aliasSpan 日期字段")


# ─────────────────────────────────────────────────────────────────
# 多选下拉筛选
# ─────────────────────────────────────────────────────────────────

def _apply_multiselect_filter(page, filter_name: str, options: List[str]):
    print(f"  设置多选筛选: {filter_name} = {options}")

    # 精确定位: 找到 aliasSpan，向上到 TR，在 TR 内找 combobox-button
    input_info = page.evaluate(f'''
        () => {{
            const spans = document.querySelectorAll('span.aliasSpan');
            for (const span of spans) {{
                if (span.textContent.trim() === '{filter_name}') {{
                    let tr = span.closest('tr');
                    if (tr) {{
                        const btn = tr.querySelector('input.combobox-button');
                        if (btn) {{
                            const rect = btn.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {{
                                return {{ found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2 }};
                            }}
                        }}
                    }}
                }}
            }}
            return {{ found: false }};
        }}
    ''')

    if not input_info.get('found'):
        print(f"    ⚠️ 未找到筛选器: {filter_name}")
        return

    # 点击 combobox-button 弹出下拉列表
    page.mouse.click(input_info['x'], input_info['y'])
    time.sleep(2)
    print(f"    ✓ 点击下拉按钮")

    # 选择选项（用坐标点击，JS click 对 Smartbi 复选框不生效）
    for option in options:
        print(f"    选择: {option}")
        opt_info = page.evaluate(f'''
            () => {{
                const items = document.querySelectorAll('.dropdown-box-span');
                for (const item of items) {{
                    if (item.textContent.trim() === '{option}') {{
                        const rect = item.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {{
                            return {{ found: true, x: rect.x + rect.width/2, y: rect.y + rect.height/2 }};
                        }}
                    }}
                }}
                return {{ found: false }};
            }}
        ''')
        if opt_info and opt_info.get('found'):
            page.mouse.click(opt_info['x'], opt_info['y'])
            time.sleep(1)
            print(f"    ✓ 已点击: {option}")
        else:
            print(f"    ⚠️ 未找到选项: {option}")
        time.sleep(1)

    # 确定
    page.evaluate('''
        () => {
            const buttons = document.querySelectorAll('button, input[type="button"]');
            for (const btn of buttons) {
                const text = (btn.textContent || btn.value || '').trim();
                if (text === '确定' || text === '确认') {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
    ''')
    time.sleep(2)

    # 刷新
    refresh = page.query_selector('input[title="刷新"]')
    if refresh:
        refresh.click()
    else:
        page.mouse.click(117, 88)
    time.sleep(10)
    print("  ✓ 多选筛选已应用")


# ─────────────────────────────────────────────────────────────────
# 版本检测 & 导出
# ─────────────────────────────────────────────────────────────────

def _click_online_export(page) -> bool:
    """查找并点击「在线导出」按钮，支持重试."""
    for attempt in range(3):
        # 方式1: Playwright getByText（精确匹配）
        try:
            btn = page.get_by_text("在线导出", exact=True).first
            if btn.is_visible(timeout=3000):
                btn.click(timeout=5000)
                time.sleep(1)
                print("  ✓ 点击「在线导出」")
                return True
        except Exception:
            pass

        # 方式2: Playwright text 选择器
        try:
            btn = page.locator("text=在线导出").first
            if btn.is_visible(timeout=3000):
                btn.click(timeout=5000)
                time.sleep(1)
                print("  ✓ 点击「在线导出」")
                return True
        except Exception:
            pass

        # 方式3: JS 查找所有可见元素
        info = page.evaluate('''
            () => {
                for (const el of document.querySelectorAll('*')) {
                    const t = (el.textContent || '').trim();
                    if (t === '在线导出' || t.includes('在线导出')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0)
                            return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                }
                return null;
            }
        ''')
        if info:
            page.mouse.click(info["x"], info["y"])
            time.sleep(1)
            print("  ✓ 点击「在线导出」(JS)")
            return True

        if attempt < 2:
            time.sleep(2)

    return False


def _do_export(page):
    """统一导出流程：点击导出 → 点击 Excel/EXCEL → 点击在线导出."""
    time.sleep(1)

    # ── 步骤1: 点击「导出」按钮 ──
    clicked = False
    # 尝试标准选择器
    for sel in ['input[title="导出"]', 'input._btnExport', 'input[value="导出"]']:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click(timeout=5000)
                time.sleep(2)
                print("  ✓ 点击「导出」")
                clicked = True
                break
        except Exception:
            continue
    # JavaScript 查找
    if not clicked:
        info = page.evaluate('''
            () => {
                for (const el of document.querySelectorAll('input[type="button"], button, i, div[title]')) {
                    const t = (el.value || el.title || el.className || '').toString().toLowerCase();
                    if (t.includes('导出') || t.includes('export')) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0 && r.width < 200)
                            return { x: r.x + r.width/2, y: r.y + r.height/2 };
                    }
                }
                return null;
            }
        ''')
        if info:
            page.mouse.click(info["x"], info["y"])
            time.sleep(2)
            print("  ✓ 点击「导出」(JS)")
            clicked = True
    if not clicked:
        print("  ✗ 未找到导出按钮")
        return

    # ── 步骤2: 点击 Excel/EXCEL ──
    excel_info = page.evaluate('''
        () => {
            for (const el of document.querySelectorAll('*')) {
                const t = (el.textContent || '').trim();
                if ((t === 'Excel' || t === 'EXCEL') && el.children.length === 0) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && r.height < 80)
                        return { x: r.x + r.width/2, y: r.y + r.height/2, text: t };
                }
            }
            return null;
        }
    ''')
    if not excel_info:
        print("  ✗ 未找到 Excel/EXCEL")
        return
    print(f"  ✓ 找到「{excel_info['text']}」at ({excel_info['x']:.0f}, {excel_info['y']:.0f})")

    # 先 hover Excel 触发子菜单（新版报表），再 click（旧版报表）
    page.mouse.move(excel_info["x"], excel_info["y"])
    time.sleep(1)
    # 检查 hover 后是否出现子菜单
    has_submenu = _click_online_export(page)
    if has_submenu:
        print(f"  ✓ hover「{excel_info['text']}」后找到「在线导出」")
    else:
        # fallback: 直接 click Excel
        page.mouse.click(excel_info["x"], excel_info["y"])
        time.sleep(2)
        print(f"  ✓ 点击「{excel_info['text']}」")
        clicked_online = _click_online_export(page)
        if not clicked_online:
            print("  ⚠ 未找到「在线导出」，等待下载...")



# ─────────────────────────────────────────────────────────────────
# 下载等待 & 保存
# ─────────────────────────────────────────────────────────────────

def _wait_download(context, page, output_dir: Path, timeout: int = 180):
    """等待文件下载，优先 Playwright download 事件，fallback 扫描目录."""
    print("  → 等待服务端生成文件并下载...")
    try:
        download = page.wait_for_event("download", timeout=timeout * 1000)
        fname = download.suggested_filename
        filepath = str(output_dir / fname)
        download.save_as(filepath)
        return filepath
    except Exception as e:
        print(f"  ⚠️ 下载事件超时: {e}")
        time.sleep(5)

    # Fallback：扫描下载目录
    latest = _get_latest_excel(output_dir)
    if latest:
        return latest
    return _get_latest_file(output_dir)


def _get_latest_excel(directory: Path) -> Optional[str]:
    excel_files = [f for f in directory.iterdir()
                   if f.is_file() and f.suffix.lower() in (".xlsx", ".xls")]
    if not excel_files:
        return None
    return str(max(excel_files, key=lambda f: f.stat().st_mtime))


def _get_latest_file(directory: Path) -> Optional[str]:
    files = [f for f in directory.iterdir() if f.is_file()]
    if not files:
        return None
    return str(max(files, key=lambda f: f.stat().st_mtime))


def _wait_refresh(page):
    try:
        page.wait_for_selector("[class*='loading']", state="hidden", timeout=10000)
    except Exception:
        pass
    time.sleep(2)


# ─────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────

def _parse_filters(raw: str) -> dict:
    if not raw:
        return {}
    result = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            k, v = item.split("=", 1)
        elif ":" in item:
            k, v = item.split(":", 1)
        else:
            continue
        result[k.strip()] = v.strip()
    return result


def _parse_kv(raw: str) -> tuple:
    if "=" in raw:
        parts = raw.split("=", 1)
    elif ":" in raw:
        parts = raw.split(":", 1)
    else:
        parts = [raw, ""]
    return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""


# ══════════════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 bi_skill.py search --name <报表名> [--path <路径>] [--filters <条件>] [--start-date ...] [--end-date ...] [--ms-filter ...] [--ms-options ...]")
        print("  python3 bi_skill.py process --input <文件> --action <操作> [--params <参数>]")
        sys.exit(1)

    sub = sys.argv[1]
    if sub == "search":
        parser = _make_search_parser()
        args, _ = parser.parse_known_args(sys.argv[2:])
        if not args.name and not args.path:
            print("[ERROR] 请指定 --name 或 --path")
            sys.exit(1)
        do_search(args)
    elif sub == "process":
        parser = _make_process_parser()
        args, _ = parser.parse_known_args(sys.argv[2:])
        do_process(args)
    else:
        print(f"未知子命令: {sub}")
        sys.exit(1)


if __name__ == "__main__":
    main()
