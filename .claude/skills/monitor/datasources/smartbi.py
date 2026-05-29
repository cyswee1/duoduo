"""Smartbi BI 报表数据源 — 参数化版本。"""
import os
import sys
import time
import shutil
from datetime import datetime, timedelta
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

        # 复用 bi_skill 的导出函数（直接从文件加载，避免 sys.path 缓存问题）
        _this_file = Path(os.path.abspath(__file__))
        skill_dir_cfg = config.get("skill_dir_key", "")
        if skill_dir_cfg:
            skill_dir = Path(skill_dir_cfg).expanduser()
        else:
            skill_dir = _this_file.parent.parent.parent / "bi_skill"
        bi_skill_file = str((skill_dir / "bi_skill.py").resolve())
        import importlib.util
        spec = importlib.util.spec_from_file_location("bi_skill", bi_skill_file)
        _bi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_bi)
        self._do_export = _bi._do_export
        self._check_session_timeout = _bi._check_session_timeout

    def _use_headless(self):
        """是否使用无头浏览器。CI 默认启用。"""
        env_val = os.environ.get("MONITOR_SMARTBI_HEADLESS", "").strip().lower()
        if env_val in ("1", "true", "yes", "on"):
            return True
        if env_val in ("0", "false", "no", "off"):
            return False
        if "headless" in self.config:
            return bool(self.config["headless"])
        return os.environ.get("CI", "").strip().lower() == "true"

    def _browser_channel(self):
        """浏览器 channel；CI 默认不指定，使用 playwright 自带 chromium。"""
        env_val = os.environ.get("MONITOR_SMARTBI_BROWSER_CHANNEL", "").strip()
        if env_val:
            return env_val
        return self.config.get("browser_channel", "")

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

        print(f"[Smartbi] 下载报表: {report_cfg['name']}")

        launch_kwargs = {"headless": self._use_headless()}
        channel = self._browser_channel()
        if channel:
            launch_kwargs["channel"] = channel

        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()

            self._login(page)
            self._enter_analysis(page)
            time.sleep(3)
            self._search_and_open(page, report_cfg["name"])
            time.sleep(report_cfg.get("wait_after_open", 5))

            # 应用日期筛选（xpath 方式）
            for filter_cfg in report_cfg.get("date_filters", []):
                xpath = filter_cfg.get("xpath")
                input_index = filter_cfg.get("input_index")
                value = filter_cfg["value"].format(**resolved_vars)
                if input_index is not None:
                    self._set_date_by_input_index(page, input_index, value)
                elif xpath:
                    self._set_date_by_xpath(page, xpath, value)
                time.sleep(2)

            # 应用 end_date_offset_hours（aliasSpan 方式）
            offset_hours = report_cfg.get("end_date_offset_hours")
            if offset_hours is not None:
                end_dt = datetime.now() + timedelta(hours=offset_hours)
                end_date_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                self._set_date_by_alias(page, "结束时间*", end_date_str)
                time.sleep(2)

            # 刷新并等待
            if report_cfg.get("date_filters") or offset_hours is not None:
                self._click_refresh(page)
                wait_time = report_cfg.get("wait_after_filter", 60)
                print(f"  等待查询完成 ({wait_time}s)...")
                time.sleep(wait_time)

            # 导出
            filepath = self._export_and_wait(page, output_dir, timeout=600)
            if filepath:
                if target.exists():
                    target.unlink()
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
        search.wait_for(state="visible", timeout=30000)
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

    def _set_date_by_input_index(self, page, input_index: int, value: str):
        """按页面上可见 input[type=text] 的顺序（跳过搜索框）设置日期值"""
        print(f"  设置日期 input[{input_index}]: {value}")
        result = page.evaluate(f'''
            () => {{
                // 排除搜索框（宽度很小或位于顶部）
                const inputs = Array.from(document.querySelectorAll('input[type="text"]'))
                    .filter(i => {{
                        const r = i.getBoundingClientRect();
                        return r.width > 50 && r.height > 10 && r.y > 50;
                    }});
                const inp = inputs[{input_index}];
                if (!inp) return {{ found: false }};
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(inp, '{value}');
                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return {{ found: true, value: inp.value }};
            }}
        ''')
        if result.get('found'):
            print(f"    ✓ 已设置: {result['value']}")
        else:
            print(f"    ✗ 未找到 input[{input_index}]")

    def _set_date_by_alias(self, page, field_name: str, date_value: str):
        """通过 aliasSpan 定位筛选器并用 JS 设置日期值（支持带时间的格式）"""
        print(f"  设置 {field_name}: {date_value}")
        result = page.evaluate(f'''
            () => {{
                const spans = document.querySelectorAll('span.aliasSpan');
                for (const span of spans) {{
                    const t = span.textContent.trim();
                    if (t === '{field_name}' || t === '{field_name}：' || t === '{field_name}:') {{
                        const tr = span.closest('tr');
                        if (tr) {{
                            const inp = tr.querySelector('input[type="text"]');
                            if (inp) {{
                                const setter = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value').set;
                                setter.call(inp, '{date_value}');
                                inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                inp.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                                return {{ success: true, value: inp.value }};
                            }}
                        }}
                    }}
                }}
                return {{ success: false }};
            }}
        ''')
        if result.get('success'):
            print(f"    ✓ 已设置: {result['value']}")
        else:
            print(f"    ✗ 未找到字段: {field_name}")

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
