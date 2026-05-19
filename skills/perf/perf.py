#!/usr/bin/env python3
"""
海外思维 LP 转介绍激励计算
Usage: python3 perf.py --month 5 --year 2026 --base-dir ~/Desktop/claude/激励
"""
import argparse, os, sys, time, warnings
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')

BI_URL = os.environ.get("BI_URL", "")
BI_USER = os.environ.get("BI_USERNAME", "")
BI_PASS = os.environ.get("BI_PASSWORD", "")

# Team filters
VALID_TEAMS = set(t.strip() for t in os.environ.get("VALID_TEAMS", "").split(",") if t.strip())
VALID_TEAMS_ROLLING = set(t.strip() for t in os.environ.get("VALID_TEAMS_ROLLING", "").split(",") if t.strip())

# ================================================================
# CLI
# ================================================================
def parse_args():
    now = datetime.now()
    p = argparse.ArgumentParser(description='海外思维 LP 转介绍激励计算')
    p.add_argument('--month', type=int, default=now.month)
    p.add_argument('--year', type=int, default=now.year)
    p.add_argument('--base-dir', type=str, default=f'{Path.home()}/Desktop/claude/激励')
    p.add_argument('--skip-download', action='store_true', help='跳过 BI 下载')
    p.add_argument('--skip-incentive', action='store_true', help='只生成业绩明细')
    return p.parse_args()


# ================================================================
# Part A: BI Download
# ================================================================
def ensure_playwright():
    try:
        import playwright
    except ImportError:
        os.system('pip3 install playwright pandas openpyxl')
    # Check chromium
    import subprocess
    r = subprocess.run(['python3', '-c', 'from playwright.sync_api import sync_playwright; pw = sync_playwright().start(); print(pw.chromium.executable_path); pw.stop()'], capture_output=True, text=True)
    if r.returncode != 0:
        os.system('python3 -m playwright install chromium 2>&1')


def download_sales_detail(base_dir, year, month):
    """Download monthly sales detail with 转介绍 channel filter for current month."""
    from playwright.sync_api import sync_playwright
    import calendar
    sys.path.insert(0, str(Path(__file__).parent.parent / 'bi_skill'))
    from bi_skill import _apply_date_filter_v2, _apply_multiselect_filter, _do_export, _wait_download, _check_session_timeout

    m_str = f'{month:02d}'
    last_day = calendar.monthrange(year, month)[1]
    start_date = f'{year}-{m_str}-01'
    end_date = f'{year}-{m_str}-{last_day:02d}'
    report_name = os.environ.get("BI_REPORT_SALES_DETAIL", "")
    target = Path(base_dir) / '销售明细-当月+重复进线.xlsx'
    if target.exists(): target.unlink()

    print(f"  下载: {report_name}")
    print(f"  筛选: 末次进线渠道一级分类=转介绍, 日期={start_date}~{end_date}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)
        _search_and_open(page, report_name)
        _check_refresh(page)

        # 设置日期筛选
        _apply_date_filter_v2(page, "末次渠道时间开始", start_date)
        time.sleep(1)
        _apply_date_filter_v2(page, "末次渠道时间结束", end_date)
        time.sleep(1)

        # 设置多选筛选
        _apply_multiselect_filter(page, "末次进线渠道一级分类", ["转介绍"])
        time.sleep(1)

        # 点击刷新
        _check_session_timeout(page)
        page.evaluate('''
            () => { for (const el of document.querySelectorAll('input[type="button"]'))
                if ((el.title||'').includes('刷新')) { el.click(); return; } }
        ''')
        time.sleep(12)

        # 导出
        _check_session_timeout(page)
        _do_export(page)

        # 等待下载
        import shutil
        filepath = _wait_download(ctx, page, Path(base_dir))
        if filepath:
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
        else:
            print("    ❌ 下载失败")

        browser.close()
        return filepath


def download_broadcast(base_dir, year, month):
    """Search and download 业绩播报."""
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(Path(__file__).parent.parent / 'bi_skill'))
    from bi_skill import _do_export, _wait_download, _check_session_timeout

    target = Path(base_dir) / '业绩播报.xlsx'
    if target.exists(): target.unlink()

    print(f"  下载: {os.environ.get('BI_REPORT_PROGRESS', '')}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)
        _search_and_open(page, os.environ.get("BI_REPORT_PROGRESS", ""))
        _check_refresh(page)
        _check_session_timeout(page)
        _do_export(page)

        import shutil
        filepath = _wait_download(ctx, page, Path(base_dir))
        if filepath:
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
        else:
            print("    ❌ 下载失败")

        browser.close()
        return filepath


def download_lp_structure(base_dir, year, month):
    """Search and download LP structure report."""
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(Path(__file__).parent.parent / 'bi_skill'))
    from bi_skill import _do_export, _wait_download, _check_session_timeout

    target = Path(base_dir) / (os.environ.get("BI_REPORT_LP_STRUCTURE", "") + ".xlsx")
    if target.exists(): target.unlink()

    print(f"  下载: {os.environ.get('BI_REPORT_LP_STRUCTURE', '')}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)
        _search_and_open(page, os.environ.get("BI_REPORT_LP_STRUCTURE", ""))
        _check_refresh(page)
        _check_session_timeout(page)
        _do_export(page)

        import shutil
        filepath = _wait_download(ctx, page, Path(base_dir))
        if filepath:
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
        else:
            print("    ❌ 下载失败")

        browser.close()
        return filepath


def download_rolling(base_dir, year, month):
    """Download rolling-conversion sales detail with specific date filters."""
    from playwright.sync_api import sync_playwright
    import calendar
    sys.path.insert(0, str(Path(__file__).parent.parent / 'bi_skill'))
    from bi_skill import _apply_date_filter_v2, _apply_multiselect_filter, _do_export, _wait_download, _check_session_timeout

    target = Path(base_dir) / '小组-滚动成单.xlsx'
    if target.exists(): target.unlink()

    # 计算当月最后一天
    last_day = calendar.monthrange(year, month)[1]
    m_str = f'{month:02d}'
    end_date = f'{year}-{m_str}-{last_day:02d}'
    start_month = f'{year}-{m_str}-01'

    report_name = os.environ.get("BI_REPORT_SALES_DETAIL", "")
    print(f"  下载: 小组-滚动成单")
    print(f"  报表: {report_name}")
    print(f"  筛选: 末次渠道时间=2020-01-01~{end_date}, 首签时间={start_month}~{end_date}, 末次进线渠道一级分类=转介绍")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=False)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        _login_bi(page)
        _enter_analysis(page)
        time.sleep(3)
        _search_and_open(page, report_name)
        _check_refresh(page)

        # 设置日期筛选
        _apply_date_filter_v2(page, "末次渠道时间开始", "2020-01-01")
        time.sleep(1)
        _apply_date_filter_v2(page, "末次渠道时间结束", end_date)
        time.sleep(1)
        _apply_date_filter_v2(page, "首签开始时间", start_month)
        time.sleep(1)
        _apply_date_filter_v2(page, "首签结束时间", end_date)
        time.sleep(1)

        # 设置多选筛选
        _apply_multiselect_filter(page, "末次进线渠道一级分类", ["转介绍"])

        # 导出
        _check_session_timeout(page)
        _do_export(page)

        # 等待下载
        print("  等待下载...")
        filepath = _wait_download(ctx, page, Path(base_dir))
        if filepath:
            # 重命名为目标文件名
            import shutil
            shutil.move(filepath, str(target))
            print(f"    => {target}")
            filepath = str(target)
        else:
            print("    ❌ 下载失败")

        browser.close()
        return filepath


# ── BI helpers ──
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
    search = page.locator("div.base__task-tree-search-row input").first
    search.click(); search.fill(name); search.press("Enter")
    time.sleep(5)
    for _ in range(2):
        page.evaluate(f'''
            () => {{
                for (const a of document.querySelectorAll('a'))
                    if (a.textContent.trim() === '{name}')
                        {{ a.dispatchEvent(new MouseEvent('dblclick', {{bubbles:true}})); return; }}
            }}
        ''')
        time.sleep(5)
    page.wait_for_load_state("networkidle")
    time.sleep(5)

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





# ================================================================
# Part B: Generate 业绩明细
# ================================================================
def generate_detail(base_dir, year, month):
    """Generate 业绩明细 sheet from source files."""
    m_str = f'{year}-{month:02d}'
    yr = str(year)[-2:]
    out_file = Path(base_dir) / f'{yr}年{month}月海外思维转介绍激励.xlsx'

    print("\n[生成业绩明细]")

    # Load 销售明细
    xs_file = Path(base_dir) / '销售明细-当月+重复进线.xlsx'
    if not xs_file.exists():
        print(f"  ❌ 缺少文件: {xs_file}")
        return None
    df_raw = pd.read_excel(xs_file, header=None)
    df_xs = df_raw.iloc[8:].copy(); df_xs.columns = df_raw.iloc[7].tolist()
    df_xs['首签金额'] = pd.to_numeric(df_xs['首签金额'], errors='coerce').fillna(0)
    df_xs['转介绍-是否重复进线'] = pd.to_numeric(df_xs['转介绍-是否重复进线'], errors='coerce').fillna(0)

    # Filter by team
    xs_filtered = df_xs[df_xs['业绩归属lp_团队'].apply(
        lambda t: str(t) if pd.notna(t) else '').isin(VALID_TEAMS)]

    rows = []
    for _, r in xs_filtered.iterrows():
        is_repeat = int(r['转介绍-是否重复进线'])
        perf_type = '重复进线例子' if is_repeat == 1 else '当月例子'
        rows.append(_build_detail_row(r, perf_type, perf_time='lead'))

    n_examples = len(rows)

    # Load 滚动成单
    gd_file = Path(base_dir) / '小组-滚动成单.xlsx'
    if gd_file.exists():
        df_raw = pd.read_excel(gd_file, header=None)
        df_gd = df_raw.iloc[8:].copy(); df_gd.columns = df_raw.iloc[7].tolist()
        df_gd['首签金额'] = pd.to_numeric(df_gd['首签金额'], errors='coerce').fillna(0)
        rolling_mask = (
            (df_gd['末次渠道更新月份'].astype(str) != m_str) &
            (df_gd['推荐人业绩归属（首消）'].astype(str) == '班主任') &
            (df_gd['业绩归属lp_团队'].apply(lambda t: str(t) if pd.notna(t) else '').isin(VALID_TEAMS_ROLLING))
        )
        rolling = df_gd[rolling_mask]
        for _, r in rolling.iterrows():
            rows.append(_build_detail_row(r, '滚动成单', perf_time='deal'))
        n_rolling = len(rolling)
    else:
        print(f"  ⚠ 未找到滚动成单文件，跳过")
        n_rolling = 0

    # Build dataframe
    df_detail = pd.DataFrame(rows)
    cols = ['ID','业绩类型','业绩LP','业绩小组','末次渠道更新时间','约课时间','到课时间','成单时间','GMV','业绩时间']
    df_detail = df_detail[cols]
    df_detail['_s'] = df_detail['业绩类型'].map({'当月例子':0,'重复进线例子':1,'滚动成单':2})
    df_detail = df_detail.sort_values('_s').drop(columns=['_s']).reset_index(drop=True)

    # Write
    mode = 'a' if out_file.exists() else 'w'
    extra = {'if_sheet_exists': 'replace'} if mode == 'a' else {}
    with pd.ExcelWriter(out_file, engine='openpyxl', mode=mode, **extra) as writer:
        df_detail.to_excel(writer, sheet_name='业绩明细', index=False)

    print(f"  ✅ 业绩明细: {len(df_detail)} 行 ({n_examples} 例子 + {n_rolling} 滚动)")
    print(f"     当月例子: {(df_detail['业绩类型']=='当月例子').sum()}")
    print(f"     重复进线例子: {(df_detail['业绩类型']=='重复进线例子').sum()}")
    print(f"     滚动成单: {(df_detail['业绩类型']=='滚动成单').sum()}")
    print(f"     GMV 合计: {df_detail['GMV'].sum():.0f}")

    return df_detail


def _build_detail_row(r, perf_type, perf_time='lead'):
    """Build a single detail row from a source data row."""
    perf_time_val = r['末次渠道更新时间'] if perf_time == 'lead' else r['首签时间']
    return {
        'ID': r['学员ID'] if pd.notna(r.get('学员ID', r.get('末次渠道变更ID'))) else '',
        '业绩类型': perf_type,
        '业绩LP': r['业绩归属lp_姓名'] if pd.notna(r.get('业绩归属lp_姓名')) else '',
        '业绩小组': r['业绩归属lp_小组'] if pd.notna(r.get('业绩归属lp_小组')) else '',
        '末次渠道更新时间': r['末次渠道更新时间'] if pd.notna(r.get('末次渠道更新时间')) else '',
        '约课时间': r['首次体验课约课时间'] if pd.notna(r.get('首次体验课约课时间')) else '',
        '到课时间': r['首次体验课出席时间'] if pd.notna(r.get('首次体验课出席时间')) else '',
        '成单时间': r['首签时间'] if pd.notna(r.get('首签时间')) else '',
        'GMV': r['首签金额'],
        '业绩时间': perf_time_val if pd.notna(perf_time_val) else '',
    }


# ================================================================
# Part C: LP 激励计算
# ================================================================
def calculate_incentives(base_dir, year, month):
    """Calculate LP incentives from source files."""
    m_str = f'{year}-{month:02d}'
    yr = str(year)[-2:]
    out_file = Path(base_dir) / f'{yr}年{month}月海外思维转介绍激励.xlsx'

    print("\n[计算 LP 激励]")

    # 1. LP 架构表
    print("  [1/5] LP架构表...")
    lps = _load_lp_structure(base_dir, year, month)
    print(f"    在职 LP: {len(lps)}")

    # 2. 业绩播报
    print("  [2/5] 业绩播报...")
    df_bc, group_data = _load_broadcast(base_dir)
    print(f"    播报 LP: {len(df_bc)}, 小组: {list(group_data.keys())}")

    # 3. 销售明细 (filtered)
    print("  [3/5] 销售明细...")
    xs_file = Path(base_dir) / '销售明细-当月+重复进线.xlsx'
    df_raw = pd.read_excel(xs_file, header=None)
    df_xs = df_raw.iloc[8:].copy(); df_xs.columns = df_raw.iloc[7].tolist()
    for c in ['首签金额','转介绍-是否重复进线','到课次数','新签退费金额']:
        df_xs[c] = pd.to_numeric(df_xs[c], errors='coerce').fillna(0)
    df_xs = df_xs[df_xs['业绩归属lp_团队'].apply(lambda t: str(t) if pd.notna(t) else '').isin(VALID_TEAMS)]
    print(f"    行数: {len(df_xs)}")

    # 4. 滚动成单
    print("  [4/5] 滚动成单...")
    gd_file = Path(base_dir) / '小组-滚动成单.xlsx'
    df_rolling = pd.DataFrame()
    if gd_file.exists():
        df_raw = pd.read_excel(gd_file, header=None)
        df_gd = df_raw.iloc[8:].copy(); df_gd.columns = df_raw.iloc[7].tolist()
        df_gd['首签金额'] = pd.to_numeric(df_gd['首签金额'], errors='coerce').fillna(0)
        df_gd['新签退费金额'] = pd.to_numeric(df_gd['新签退费金额'], errors='coerce').fillna(0)
        rolling_mask = (
            (df_gd['末次渠道更新月份'].astype(str) != m_str) &
            (df_gd['推荐人业绩归属（首消）'].astype(str) == '班主任') &
            (df_gd['业绩归属lp_团队'].apply(lambda t: str(t) if pd.notna(t) else '').isin(VALID_TEAMS_ROLLING))
        )
        df_rolling = df_gd[rolling_mask].copy()
    print(f"    行数: {len(df_rolling)}")

    # 5. Compute & calculate
    print("  [5/5] 计算激励...")
    df_metrics = _compute_metrics(lps, df_xs, df_rolling, df_bc)
    df_out = _apply_incentives(df_metrics, group_data)
    out = _build_output(df_out)

    # Write
    mode = 'a' if out_file.exists() else 'w'
    extra = {'if_sheet_exists': 'replace'} if mode == 'a' else {}
    with pd.ExcelWriter(out_file, engine='openpyxl', mode=mode, **extra) as writer:
        out.to_excel(writer, sheet_name='LP激励', index=False)

    # Summary
    today = datetime.now()
    vel_col = f'个人流速奖金池\n——截止{today.month}.{today.day}'
    print(f"  ✅ LP激励: {len(out)} 行")
    print(f"     非港澳: {(out['区域']=='非港澳').sum()} | 港澳: {(out['区域']=='港澳').sum()}")
    print(f"     打卡率达标: {out['是否达成打卡率门槛'].sum()} ({out['是否达成打卡率门槛'].mean():.1%})")
    print(f"     例子绩效: {out['例子绩效'].sum():.0f}")
    print(f"     成单激励: {out['成单激励'].sum():.0f}")
    print(f"     到课激励: {out['到课例子激励'].sum():.0f}")
    print(f"     排名激励: {out['例子排名激励'].sum():.0f}")
    print(f"     流速奖金池: {out[vel_col].sum():.0f}")
    print(f"     总激励+绩效: {out['总激励+绩效'].sum():.2f}")

    # Top 10
    print(f"\n  Top 10:")
    for _, r in out.head(10).iterrows():
        print(f"    {r['LP姓名']:6s} | {str(r['小组']):6s} | 例子={int(r['总例子'])} | 总激励={r['总激励+绩效']:.0f}")

    return out


def _load_lp_structure(base_dir, year, month):
    df_raw = pd.read_excel(Path(base_dir) / (os.environ.get("BI_REPORT_LP_STRUCTURE", "") + ".xlsx"), sheet_name=os.environ.get("BI_REPORT_LP_STRUCTURE", ""), header=None)
    df = df_raw.iloc[4:].copy()
    df.columns = ['大区','团队','团队id','小组','小组id','主管','姓名','员工编号','人员id',
                  '入职时间','离职日期','是否在职','入职时长月份','入职时长分组','职位','职级2']
    df['入职时间'] = pd.to_datetime(df['入职时间'])
    # 同时担任 TL 和 LP 的人员需额外纳入 LP 列表(默认空,通过 EXTRA_LP_NAMES 环境变量传入,逗号分隔)
    extra_lp_names = [n.strip() for n in os.environ.get("EXTRA_LP_NAMES", "").split(",") if n.strip()]
    active = df[(df['是否在职'] == '在职') &
                ((df['职位'] == '班主任') | (df['姓名'].isin(extra_lp_names)))].copy()
    active['区域'] = active['团队'].apply(lambda t: '港澳' if '港澳' in str(t) else '非港澳')
    month_start = pd.Timestamp(f'{year}-{month:02d}-01')
    active['当月入职'] = active['入职时间'] >= month_start
    return active


def _load_broadcast(base_dir):
    df_raw = pd.read_excel(Path(base_dir)/'业绩播报.xlsx', sheet_name='Sheet1', header=None)
    lp_data = []; group_data = {}
    in_group = False; in_lp = False; last_path = ''

    for i in range(len(df_raw)):
        row = df_raw.iloc[i]
        c1 = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
        c2 = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ''
        c3 = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ''

        if '海外-小组' in c1: in_group = True; in_lp = False
        if '海外-LP' in c1: in_group = False; in_lp = True; last_path = c2

        if in_group and c3 == '总计':
            gp = c2.split('~')[-1] if '~' in c2 else c2
            group_data[gp] = {
                'g_M1M3': float(row.iloc[46]) if pd.notna(row.iloc[46]) else None,
                'g_M1M3_target': float(row.iloc[45]) if pd.notna(row.iloc[45]) else None,
            }
        if in_lp and c3 and c3 not in ('总计','LP','标识'):
            tp = c2 if c2 else last_path
            if c2: last_path = c2
            lp_data.append({
                '姓名': c3, '例子目标': int(row.iloc[12]) if pd.notna(row.iloc[12]) else 0,
                'M1-M3打卡率': float(row.iloc[46]) if pd.notna(row.iloc[46]) else None,
                'GMV目标': float(row.iloc[33]) if pd.notna(row.iloc[33]) else 0,
            })
    return pd.DataFrame(lp_data), group_data


def _compute_metrics(lps, df_xs, df_rolling, df_bc):
    results = []
    for _, lp in lps.iterrows():
        name = lp['姓名']; team = lp['团队']; group = lp['小组']
        region = lp['区域']; is_new = lp['当月入职']

        xs_lp = df_xs[df_xs['业绩归属lp_姓名'] == name]
        当月例子 = int((xs_lp['转介绍-是否重复进线'] == 0).sum())
        重复进线例子 = int((xs_lp['转介绍-是否重复进线'] == 1).sum())
        当月成单 = int(((xs_lp['首签金额'] > 0) & (xs_lp['转介绍-是否重复进线'] == 0)).sum())
        重复成单 = int(((xs_lp['首签金额'] > 0) & (xs_lp['转介绍-是否重复进线'] == 1)).sum())
        gmv_xs = xs_lp['首签金额'].sum() - xs_lp['新签退费金额'].sum()
        到课 = int(xs_lp['到课次数'].sum())

        gd_lp = df_rolling[df_rolling['业绩归属lp_姓名'] == name]
        滚动成单 = len(gd_lp)
        gmv_rolling = gd_lp['首签金额'].sum() - gd_lp.get('新签退费金额', pd.Series([0]*len(gd_lp))).sum()

        总例子 = 当月例子 + 重复进线例子
        总成单 = 当月成单 + 重复成单 + 滚动成单
        gmv_total = gmv_xs + gmv_rolling

        bc_row = df_bc[df_bc['姓名'] == name]
        例子目标 = 0; gmv_target = 0; m1m3_rate = None
        if len(bc_row) > 0:
            bc = bc_row.iloc[0]
            例子目标 = int(bc['例子目标']) if pd.notna(bc['例子目标']) else 0
            gmv_target = float(bc['GMV目标']) if pd.notna(bc['GMV目标']) else 0
            m1m3_rate = float(bc['M1-M3打卡率']) if pd.notna(bc['M1-M3打卡率']) else None

        例子达成 = round(总例子 / 例子目标, 6) if 例子目标 > 0 else 0.0
        gmv_rate = round(gmv_total / gmv_target, 6) if gmv_target > 0 else 0.0

        results.append({
            '姓名': name, '团队': team, '小组': group, '区域': region,
            '入职时间': lp['入职时间'], '当月入职': is_new,
            '例子目标': 例子目标, '当月例子': 当月例子, '重复进线例子': 重复进线例子,
            '勘误例子': 0, '总例子': 总例子, '例子达成': 例子达成,
            '当月成单': 当月成单, '重复进线当月成单': 重复成单,
            '滚动成单': 滚动成单, '勘误成单': 0, '总成单': 总成单,
            'GMV目标': gmv_target, 'GMV达成': gmv_total, 'GMV达成率': gmv_rate,
            'M1-M3打卡率': m1m3_rate, '到课总数': 到课,
        })
    return pd.DataFrame(results)


def _apply_incentives(df_metrics, group_data):
    def _perf_rate(r):
        if r >= 1.10: return 8
        elif r >= 1.00: return 7
        elif r >= 0.90: return 6
        elif r >= 0.75: return 5
        return 0

    def _fhk_ladder(rate, deals):
        if rate >= 0.9:
            if deals >= 8: return 180
            elif deals >= 3: return 150
            elif deals >= 1: return 120
        if rate < 0.9: return 50
        return 0

    def _hk_class_tier(n):
        if n >= 20: return 60
        elif n >= 13: return 40
        elif n >= 7: return 25
        return 10

    out_rows = []
    for _, lp in df_metrics.iterrows():
        name = lp['姓名']; group = lp['小组']; region = lp['区域']
        is_new = lp['当月入职']; ex = lp['总例子']; ex_rate = lp['例子达成']
        deals = lp['总成单']

        # Checkin gate
        gi = group_data.get(group, {})
        gm = gi.get('g_M1M3'); gt = gi.get('g_M1M3_target')
        indiv_thresh = 0.30 if '台湾' in str(lp['团队']) else 0.45
        checkin = False
        if gm is not None and gt is not None and float(gm) >= float(gt):
            checkin = True
        if not checkin:
            m1m3 = lp['M1-M3打卡率']
            if m1m3 is not None and float(m1m3) >= indiv_thresh:
                checkin = True
        gate = 1 if checkin else 0

        # 例子绩效
        pr = _perf_rate(ex_rate)
        ex_perf = ex * pr if (checkin or is_new) else 0

        # 成单 / 到课
        deal_inc = 0; class_inc = 0
        if region == '非港澳':
            if is_new: deal_inc = deals * 100
            elif checkin: deal_inc = deals * _fhk_ladder(ex_rate, deals)
        else:
            classes = lp['到课总数']; cr = _hk_class_tier(classes)
            if is_new:
                class_inc = classes * cr; deal_inc = deals * 100
            else:
                if checkin: class_inc = classes * cr
                if ex_rate >= 1.0 and checkin: deal_inc = deals * 100

        out_rows.append({
            **lp.to_dict(), '是否新人': 1 if is_new else 0,
            '是否达成打卡率门槛': gate,
            '例子绩效': ex_perf, '成单激励': deal_inc,
            '到课例子': lp['到课总数'], '到课例子激励': int(class_inc),
        })

    df_out = pd.DataFrame(out_rows)

    # Ranking
    rank_pool = df_out[((df_out['是否达成打卡率门槛'] == 1) | (df_out['是否新人'] == 1)) &
                       (df_out['GMV达成率'] >= 0.9)].copy()
    rank_pool = rank_pool.sort_values('总例子', ascending=False)
    rank_map = {}; bonus_map = {}
    seen = {}
    for idx, (i, row) in enumerate(rank_pool.iterrows()):
        val = row['总例子']
        r = seen.get(val, idx + 1)
        if val not in seen: seen[val] = idx + 1
        rank_map[i] = r
        if r == 1: bonus_map[i] = 800
        elif 2 <= r <= 3: bonus_map[i] = 600
        elif 4 <= r <= 10: bonus_map[i] = 400
        elif 11 <= r <= 20: bonus_map[i] = 200
        else: bonus_map[i] = 0

    df_out['本月例子排名'] = df_out.index.map(lambda i: rank_map.get(i, 25))
    df_out['例子排名激励'] = df_out.index.map(lambda i: bonus_map.get(i, 0))

    # Velocity pool
    vel_pool = df_out[((df_out['是否达成打卡率门槛'] == 1) | (df_out['是否新人'] == 1)) &
                      (df_out['例子达成'] >= 0.6) &
                      (df_out['小组'] != '美澳5组')].copy()
    vel_map = {}
    if len(vel_pool) > 0 and vel_pool['总例子'].sum() > 0:
        total_vel = vel_pool['总例子'].sum()
        for i, row in vel_pool.iterrows():
            share = row['总例子'] / total_vel
            vel_map[i] = min(round(share * 10000, 2), 2000)

    df_out['个人流速奖金池'] = df_out.index.map(lambda i: vel_map.get(i, 0))
    df_out['总激励+绩效'] = (df_out['例子绩效'] + df_out['成单激励'] +
                          df_out['到课例子激励'] + df_out['例子排名激励'] +
                          df_out['个人流速奖金池'])
    return df_out


def _build_output(df_out):
    df_out = df_out.sort_values('总例子', ascending=False).reset_index(drop=True)
    out = pd.DataFrame()
    out['LP姓名'] = df_out['姓名']
    out['团队'] = df_out['团队']
    out['小组'] = df_out['小组']
    out['区域'] = df_out['区域']
    out['入职时间'] = df_out['入职时间']
    out['例子目标'] = df_out['例子目标']
    out['当月例子'] = df_out['当月例子']
    out['重复进线例子'] = df_out['重复进线例子']
    out['勘误例子'] = df_out['勘误例子']
    out['总例子'] = df_out['总例子']
    out['例子达成-月'] = df_out['例子达成']
    out['当月成单'] = df_out['当月成单']
    out['重复进线当月成单'] = df_out['重复进线当月成单']
    out['滚动成单(30天）'] = df_out['滚动成单']
    out['勘误成单'] = df_out['勘误成单']
    out['总成单'] = df_out['总成单']
    out['GMV目标'] = df_out['GMV目标']
    out['GMV达成'] = df_out['GMV达成']
    out['GMV达成率'] = df_out['GMV达成率']
    out['M1-M3打卡率'] = df_out['M1-M3打卡率']
    out['是否新人'] = df_out['是否新人']
    out['是否达成打卡率门槛'] = df_out['是否达成打卡率门槛']
    out['例子绩效'] = df_out['例子绩效']
    out['成单激励'] = df_out['成单激励']
    out['到课例子'] = df_out['到课例子']
    out['到课例子激励'] = df_out['到课例子激励']
    out['本月例子排名'] = df_out['本月例子排名']
    out['例子排名激励'] = df_out['例子排名激励']
    out['个人流速-截止5.17'] = df_out['例子达成']
    today = datetime.now()
    vel_col = f'个人流速奖金池\n——截止{today.month}.{today.day}'
    out[vel_col] = df_out['个人流速奖金池']
    out['总激励+绩效'] = df_out['总激励+绩效']
    return out


# ================================================================
# Main
# ================================================================
def main():
    args = parse_args()
    base_dir = Path(args.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    year, month = args.year, args.month

    print("=" * 60)
    print(f"海外思维 LP 转介绍激励计算 — {year}年{month}月")
    print("=" * 60)

    if not args.skip_download:
        ensure_playwright()
        print("\n[步骤 1/4] 下载 BI 源数据")
        download_sales_detail(base_dir, year, month)
        download_broadcast(base_dir, year, month)
        download_lp_structure(base_dir, year, month)
        print("\n✅ BI 源数据下载完成")

        print("\n[步骤 2/4] 下载滚动成单")
        download_rolling(base_dir, year, month)
        print("\n✅ 滚动成单下载完成")
    else:
        print("\n[跳过下载]")

    print(f"\n[步骤 3/4] 生成业绩明细")
    generate_detail(base_dir, year, month)

    if not args.skip_incentive:
        print(f"\n[步骤 4/4] 计算 LP 激励")
        calculate_incentives(base_dir, year, month)

    out_file = base_dir / f'{str(year)[-2:]}年{month}月海外思维转介绍激励.xlsx'
    print(f"\n{'='*60}")
    print(f"✅ 完成! 输出: {out_file}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
