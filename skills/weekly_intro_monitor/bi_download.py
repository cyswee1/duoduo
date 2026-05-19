#!/usr/bin/env python3
"""BI报表下载模块 — 复用 bi_skill.py 的筛选/导出函数"""
import os
import sys
import time
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from config import (
    BI_REPORT_PROGRESS, BI_REPORT_FOLLOWUP,
    BI_SKILL_DIR, OUTPUT_DIR,
)

BI_URL = os.environ.get("BI_URL", "")
BI_USER = os.environ.get("BI_USERNAME", "")
BI_PASS = os.environ.get("BI_PASSWORD", "")

sys.path.insert(0, str(BI_SKILL_DIR))
from bi_skill import (
    _apply_date_filter_v2,
    _do_export,
    _check_session_timeout,
)


def _login_bi(page):
    page.goto(BI_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page.locator("input.item-textinput").first.fill(BI_USER)
    page.locator("input.item-textinput").nth(1).fill(BI_PASS)
    page.locator("input.item-submit").click()
    page.wait_for_load_state("networkidle")
    time.sleep(5)


def _enter_analysis(page):
    page.locator("span[bofid='Analysis']").first.click()
    time.sleep(3)


def _search_and_open(page, name):
    """通过搜索打开报表"""
    print(f"  搜索报表: {name}")

    # 等待搜索框出现
    try:
        search = page.locator("div.base__task-tree-search-row input").first
        search.wait_for(state="visible", timeout=10000)
    except Exception as e:
        print(f"    ⚠ 搜索框未找到: {e}")
        # 尝试其他可能的选择器
        try:
            search = page.locator("input[placeholder*='搜索']").first
            search.wait_for(state="visible", timeout=5000)
        except:
            print("    ✗ 无法定位搜索框")
            return False

    search.click()
    search.fill(name)
    search.press("Enter")
    print("    搜索完成，等待结果...")
    time.sleep(5)

    # 双击打开报表（两次）
    for attempt in range(2):
        clicked = page.evaluate(f'''
            () => {{
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === '{name}')
                        {{ a.dispatchEvent(new MouseEvent('dblclick', {{bubbles:true}})); return true; }}
                return false;
            }}
        ''')
        if clicked:
            print(f"    双击 {attempt + 1}/2")
        time.sleep(5)

    page.wait_for_load_state("networkidle", timeout=60000)
    time.sleep(5)
    print("  ✓ 报表已打开")
    return True


def _navigate_tree(page, path):
    """通过目录树路径导航到报表

    Args:
        page: Playwright page对象
        path: 路径字符串(BI 目录树形如 "业务线>部门>报表名"),具体路径通过环境变量配置
    """
    parts = [p.strip() for p in path.split('>')]
    print(f"  目录树导航: {' > '.join(parts)}")

    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        print(f"    [{i+1}/{len(parts)}] {'打开' if is_last else '展开'}: {part}")

        # 双击展开文件夹或打开报表
        result = page.evaluate(f'''
            () => {{
                const target = '{part}';
                for (const a of document.querySelectorAll('a')) {{
                    if (a.textContent.trim() === target) {{
                        a.dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}));
                        return true;
                    }}
                }}
                return false;
            }}
        ''')

        if not result:
            print(f"    ✗ 未找到: {part}")
            return False

        time.sleep(3 if is_last else 2)

    print("  ✓ 报表已打开")
    page.wait_for_load_state("networkidle", timeout=60000)
    time.sleep(5)
    return True


def _check_refresh(page):
    rc = page.evaluate('''
        () => {
            for (const s of document.querySelectorAll('span')) {
                const m = (s.textContent||'').match(/共\\s*(\\d+)\\s*行/);
                if (m) return parseInt(m[1]);
            }
            return 0;
        }
    ''')
    if rc > 0:
        print(f"    数据: {rc} 行")
    else:
        print(f"    刷新...")
        page.evaluate('''
            () => { for (const el of document.querySelectorAll('input[type="button"]'))
                if ((el.title||'').includes('刷新')) { el.click(); return; } }
        ''')
        time.sleep(10)


def _click_refresh(page):
    """点击刷新按钮"""
    _check_session_timeout(page)
    page.evaluate('''
        () => { for (const el of document.querySelectorAll('input[type="button"]'))
            if ((el.title||'').includes('刷新')) { el.click(); return; } }
    ''')
    print("    点击刷新")


def _export_and_wait(page, output_dir, timeout=600):
    """点击导出后通过 Playwright 的 download 事件捕获文件并保存到 output_dir"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 记录导出前xlsx快照（fallback用）
    before_files = {
        str(f): f.stat().st_mtime
        for f in output_dir.glob("*.xlsx")
        if not f.name.startswith('.~')
    }

    print("  → 开始导出...")
    try:
        with page.expect_download(timeout=timeout * 1000) as download_info:
            _do_export(page)
        download = download_info.value
        fname = download.suggested_filename or f"download_{int(time.time())}.xlsx"
        filepath = str(output_dir / fname)
        download.save_as(filepath)
        size = Path(filepath).stat().st_size
        print(f"  ✓ 下载完成: {fname} ({size} bytes)")
        return filepath
    except Exception as e:
        print(f"  ⚠ download 事件等待失败: {e}")

    # Fallback：扫描目录看有没有新文件
    print("  → fallback 扫描目录...")
    deadline = time.time() + 30
    while time.time() < deadline:
        for f in output_dir.glob("*.xlsx"):
            if f.name.startswith('.~'):
                continue
            fpath = str(f)
            mtime = f.stat().st_mtime
            if fpath not in before_files or mtime > before_files[fpath]:
                size1 = f.stat().st_size
                time.sleep(1)
                size2 = f.stat().st_size
                if size2 == size1 and size2 > 1000:
                    print(f"  ✓ fallback扫到: {f.name} ({size2} bytes)")
                    return fpath
        time.sleep(2)

    print(f"  ✗ 未捕获到下载文件")
    return None


def download_progress_report(output_dir=None):
    """下载业绩播报表（无需筛选，直接导出）"""
    from playwright.sync_api import sync_playwright

    output_dir = Path(output_dir or OUTPUT_DIR)
    target = output_dir / "业绩播报_监控.xlsx"
    if target.exists():
        target.unlink()

    print(f"[phase2] 下载: {BI_REPORT_PROGRESS}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)
        _search_and_open(page, BI_REPORT_PROGRESS)
        _check_refresh(page)

        _check_session_timeout(page)
        filepath = _export_and_wait(page, output_dir)
        if filepath:
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
        else:
            print("    下载失败")

        browser.close()
        return filepath


def _wait_for_query_complete(page, timeout=300):
    """等待查询完成（检测"点击图标取消查询"消失）"""
    print("    等待查询完成...")

    # 先检查是否有"点击图标取消查询"
    time.sleep(2)
    has_cancel_initial = page.evaluate('''
        () => {
            for (const el of document.querySelectorAll('*')) {
                if ((el.textContent || '').includes('点击图标取消查询')) {
                    return true;
                }
            }
            return false;
        }
    ''')

    if not has_cancel_initial:
        print("    ✓ 查询已完成（无加载提示）")
        return True

    # 如果有，等待它消失
    for _ in range(timeout):
        time.sleep(1)
        has_cancel = page.evaluate('''
            () => {
                for (const el of document.querySelectorAll('*')) {
                    if ((el.textContent || '').includes('点击图标取消查询')) {
                        return true;
                    }
                }
                return false;
            }
        ''')
        if not has_cancel:
            print("    ✓ 查询完成")
            return True
    print("    ⚠ 等待超时")
    return False


def _set_start_date_direct(page, date_value):
    """直接通过XPath设置开始时间"""
    xpath = '/html/body/div[1]/div[2]/div[1]/div/div[2]/div/div/table/tbody/tr[2]/td/div/div/table/tbody/tr/td[3]/div/div/div/div/div/div[2]/div[1]/div[4]/table/tbody/tr[2]/td/div/div/div/table/tbody/tr[2]/td/table/tbody/tr[3]/td/div[1]/div[1]/div/table/tbody/tr/td[2]/div/input[1]'

    print(f"  设置开始时间: {date_value}")

    result = page.evaluate(f'''
        () => {{
            const xpath = '{xpath}';
            const value = '{date_value}';
            const input = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (input) {{
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                nativeInputValueSetter.call(input, value);
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return {{ success: true, value: input.value }};
            }}
            return {{ success: false }};
        }}
    ''')

    if result['success']:
        print(f"    ✓ 已设置: {result['value']}")
        return True
    else:
        print(f"    ✗ 未找到输入框")
        return False
    """调试：查找页面上所有可能的日期筛选器"""
    result = page.evaluate('''
        () => {
            const filters = [];
            // 查找所有包含"时间"的文本元素
            for (const el of document.querySelectorAll('*')) {
                const text = (el.textContent || '').trim();
                if (text.includes('时间') && text.length < 50) {
                    const tag = el.tagName.toLowerCase();
                    const classes = el.className || '';
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        // 查找附近的input
                        let nearbyInput = null;
                        const parent = el.closest('tr') || el.parentElement;
                        if (parent) {
                            const input = parent.querySelector('input[type="text"]');
                            if (input) {
                                nearbyInput = {
                                    value: input.value,
                                    className: input.className
                                };
                            }
                        }
                        filters.push({
                            text: text,
                            tag: tag,
                            classes: classes,
                            nearbyInput: nearbyInput
                        });
                    }
                }
            }

            // 额外：查找所有 aliasSpan
            const aliasSpans = [];
            for (const span of document.querySelectorAll('span.aliasSpan')) {
                aliasSpans.push(span.textContent.trim());
            }

            return {filters: filters, aliasSpans: aliasSpans};
        }
    ''')
    print("  [调试] 页面上的时间筛选器：")
    for f in result['filters']:
        print(f"    - 文本: {f['text']}")
        print(f"      标签: {f['tag']}, class: {f['classes']}")
        if f['nearbyInput']:
            print(f"      附近input: value={f['nearbyInput']['value']}, class={f['nearbyInput']['className']}")
    print(f"  [调试] 所有 aliasSpan: {result['aliasSpans']}")
    return result


def download_followup_report(output_dir=None):
    """下载外呼跟进报表（搜索方式）"""
    from playwright.sync_api import sync_playwright

    output_dir = Path(output_dir or OUTPUT_DIR)
    target = output_dir / "外呼跟进_监控.xlsx"
    if target.exists():
        target.unlink()

    # 计算本周一日期
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    start_date = monday.strftime("%Y-%m-%d")

    print(f"[phase3] 下载: {BI_REPORT_FOLLOWUP}")
    print(f"  开始时间: {start_date}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)

        # 1. 搜索并双击打开报表
        _search_and_open(page, BI_REPORT_FOLLOWUP)

        # 2. 等待初始加载完成
        _wait_for_query_complete(page)

        # 3. 筛选"开始时间"为本周一
        _set_start_date_direct(page, start_date)
        time.sleep(2)

        # 4. 点击刷新
        _click_refresh(page)

        # 5. 等待刷新完成
        _wait_for_query_complete(page)

        # 6. 导出（不检查session timeout，避免误判刷新页面）
        filepath = _export_and_wait(page, output_dir, timeout=300)
        if filepath:
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
            browser.close()
        else:
            print("    下载失败，浏览器保持打开方便检查")

        return filepath


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("report", choices=["progress", "followup"])
    p.add_argument("--output", default=str(OUTPUT_DIR))
    args = p.parse_args()

    if args.report == "progress":
        download_progress_report(args.output)
    else:
        download_followup_report(args.output)
