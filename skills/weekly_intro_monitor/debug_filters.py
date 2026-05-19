#!/usr/bin/env python3
"""详细检查外呼跟进报表的筛选器"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "bi_skill"))

from playwright.sync_api import sync_playwright

BI_URL = os.environ.get("BI_URL", "")
BI_USER = os.environ.get("BI_USERNAME", "")
BI_PASS = os.environ.get("BI_PASSWORD", "")
REPORT_NAME = "思维转介绍过程跟进报表_末次渠道"

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome", headless=False)
    page = browser.new_page()

    # 登录
    page.goto(BI_URL, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    page.locator("input.item-textinput").first.fill(BI_USER)
    page.locator("input.item-textinput").nth(1).fill(BI_PASS)
    page.locator("input.item-submit").click()
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    # 进入分析展现
    page.locator("span[bofid='Analysis']").first.click()
    time.sleep(3)

    # 搜索并打开报表
    search = page.locator("div.base__task-tree-search-row input").first
    search.click()
    search.fill(REPORT_NAME)
    search.press("Enter")
    time.sleep(5)

    for _ in range(2):
        page.evaluate(f'''
            () => {{
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === '{REPORT_NAME}')
                        {{ a.dispatchEvent(new MouseEvent('dblclick', {{bubbles:true}})); return; }}
            }}
        ''')
        time.sleep(5)
    page.wait_for_load_state("networkidle")

    print("报表已打开，等待15秒让筛选器加载...")
    time.sleep(15)

    # 方法1: 查找 span.aliasSpan
    filters1 = page.evaluate('''
        () => {
            const result = [];
            const spans = document.querySelectorAll('span.aliasSpan');
            for (const span of spans) {
                const text = span.textContent.trim();
                if (text) result.push(text);
            }
            return result;
        }
    ''')
    print(f"\n方法1 (span.aliasSpan): 找到 {len(filters1)} 个")
    for f in filters1:
        print(f"  - {f}")

    # 方法2: 查找所有 input[type="text"]
    inputs = page.evaluate('''
        () => {
            const result = [];
            const inputs = document.querySelectorAll('input[type="text"]');
            for (const inp of inputs) {
                const tr = inp.closest('tr');
                if (tr) {
                    const label = tr.querySelector('span');
                    result.push({
                        label: label ? label.textContent.trim() : '',
                        placeholder: inp.placeholder || '',
                        value: inp.value || ''
                    });
                }
            }
            return result;
        }
    ''')
    print(f"\n方法2 (input[type=text]): 找到 {len(inputs)} 个")
    for inp in inputs[:10]:
        print(f"  - label: {inp['label']}, placeholder: {inp['placeholder']}, value: {inp['value']}")

    # 方法3: 截图保存
    screenshot_path = "/Users/dory/Downloads/外呼跟进报表_筛选器.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"\n已保存截图: {screenshot_path}")

    print("\n浏览器将保持打开60秒，请手动查看筛选器位置...")
    time.sleep(60)
    browser.close()
