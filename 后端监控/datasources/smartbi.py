"""Smartbi BI 报表数据源 — 参数化版本。"""
import sys
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright


class SmartbiDataSource:
    """参数化的 Smartbi BI 报表下载器"""

    def __init__(self, config, secrets_loader):
        """
        Args:
            config: datasources.smartbi 配置块
            secrets_loader: 凭证加载函数
        """
        self.config = config
        self.secrets = secrets_loader()
        self.url = self.secrets[config["url_key"]]
        self.user = self.secrets[config["user_key"]]
        self.password = self.secrets[config["pass_key"]]

        # 复用 bi_skill 的导出函数
        skill_dir = Path(config.get("skill_dir_key", "")).expanduser()
        if not skill_dir or not skill_dir.exists():
            skill_dir = Path(__file__).parent.parent.parent / "bi_skill"
        sys.path.insert(0, str(skill_dir))
        from bi_skill import _do_export, _check_session_timeout
        self._do_export = _do_export
        self._check_session_timeout = _check_session_timeout

    def download_report(self, report_name, output_dir, resolved_vars):
        """下载指定报表

        Args:
            report_name: 报表配置名（如 'progress' / 'followup'）
            output_dir: 输出目录
            resolved_vars: 模板变量字典（如 {this_monday: '2026-05-18'}）

        Returns:
            下载文件的完整路径
        """
        report_cfg = self.config["reports"][report_name]
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / report_cfg["output_filename"]
        if target.exists():
            target.unlink()

        print(f"[Smartbi] 下载报表: {report_cfg['name']}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=False)
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()

            self._login(page)
            self._enter_analysis(page)
            time.sleep(3)
            self._search_and_open(page, report_cfg["name"])
            time.sleep(report_cfg.get("wait_after_open", 5))

            # 应用日期筛选
            for filter_cfg in report_cfg.get("date_filters", []):
                xpath = filter_cfg["xpath"]
                value = filter_cfg["value"].format(**resolved_vars)
                self._set_date_by_xpath(page, xpath, value)
                time.sleep(2)

            # 刷新并等待
            if report_cfg.get("date_filters"):
                self._click_refresh(page)
                wait_time = report_cfg.get("wait_after_filter", 60)
                print(f"  等待查询完成 ({wait_time}s)...")
                time.sleep(wait_time)

            # 导出
            filepath = self._export_and_wait(page, output_dir, timeout=300)
            if filepath:
                shutil.move(filepath, str(target))
                print(f"    => {target}")
                filepath = str(target)
            else:
                print("    下载失败")

            browser.close()
            return filepath

    def _login(self, page):
        page.goto(self.url, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        page.locator("input.item-textinput").first.fill(self.user)
        page.locator("input.item-textinput").nth(1).fill(self.password)
        page.locator("input.item-submit").click()
        page.wait_for_load_state("networkidle")
        time.sleep(5)

    def _enter_analysis(self, page):
        page.locator("span[bofid='Analysis']").first.click()
        time.sleep(3)

    def _search_and_open(self, page, name):
        print(f"  搜索报表: {name}")
        search = page.locator("div.base__task-tree-search-row input").first
        search.wait_for(state="visible", timeout=10000)
        search.click()
        search.fill(name)
        search.press("Enter")
        print("    搜索完成，等待结果...")
        time.sleep(5)

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

    def _set_date_by_xpath(self, page, xpath, value):
        print(f"  设置日期筛选: {value}")
        result = page.evaluate(f'''
            () => {{
                const xpath = '{xpath}';
                const value = '{value}';
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
        if result.get('success'):
            print(f"    ✓ 已设置: {result['value']}")
        else:
            print(f"    ✗ XPath 未找到输入框")

    def _click_refresh(self, page):
        self._check_session_timeout(page)
        page.evaluate('''
            () => { for (const el of document.querySelectorAll('input[type="button"]'))
                if ((el.title||'').includes('刷新')) { el.click(); return; } }
        ''')
        print("    点击刷新")

    def _export_and_wait(self, page, output_dir, timeout=600):
        output_dir = Path(output_dir)
        before_files = {
            str(f): f.stat().st_mtime
            for f in output_dir.glob("*.xlsx")
            if not f.name.startswith('.~')
        }

        print("  → 开始导出...")
        try:
            with page.expect_download(timeout=timeout * 1000) as download_info:
                self._do_export(page)
            download = download_info.value
            fname = download.suggested_filename or f"download_{int(time.time())}.xlsx"
            filepath = str(output_dir / fname)
            download.save_as(filepath)
            size = Path(filepath).stat().st_size
            print(f"  ✓ 下载完成: {fname} ({size} bytes)")
            return filepath
        except Exception as e:
            print(f"  ⚠ download 事件等待失败: {e}")

        # Fallback
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
