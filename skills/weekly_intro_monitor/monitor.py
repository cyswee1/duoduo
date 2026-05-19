#!/usr/bin/env python3
"""每周转介绍业务监控 — 主脚本"""
import argparse
import calendar
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    TEAM_CONFIG, TARGET_POOLS, PROGRESS_THRESHOLD,
    CALL_LOW_THRESHOLD, ZERO_FOLLOWUP_WARN, MIN_CALL_WITH_ZERO_CONVERSION,
    OUTPUT_DIR,
)


def parse_args():
    p = argparse.ArgumentParser(description="每周转介绍业务监控")
    sub = p.add_subparsers(dest="phase", required=True)

    for name in ["phase1", "phase2", "phase3", "all"]:
        sp = sub.add_parser(name)
        sp.add_argument("--team", required=True, choices=["美澳", "港澳"])
        sp.add_argument("--force", action="store_true", help="跳过日期检查")
        sp.add_argument("--dry-run", action="store_true", help="只计算不发送")
        sp.add_argument("--output", default=str(OUTPUT_DIR))

    return p.parse_args()


def check_schedule(team, phase, force=False):
    """检查当前是否应该执行"""
    if force:
        return True

    now = datetime.now()
    weekday = now.weekday()
    if weekday not in (1, 2):  # 周二=1, 周三=2
        print(f"当前非周二/三（weekday={weekday}），跳过执行。使用 --force 强制执行。")
        return False

    current_time = now.strftime("%H:%M")
    config = TEAM_CONFIG[team]["schedule"]

    if phase == "phase1":
        earliest = config["phase1"]
        if current_time < earliest:
            print(f"{team}团队阶段1需在 {earliest} 后执行，当前 {current_time}")
            return False
    return True


def run_phase1(team, dry_run=False):
    """阶段1：提醒TL登记目标"""
    print(f"\n{'='*50}")
    print(f"[阶段1] 提醒TL登记目标 — {team}团队")
    print(f"{'='*50}")

    config = TEAM_CONFIG[team]
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekday_names[today.weekday()]
    deadline = config["schedule"]["phase1"].replace(":00", ":00")

    tl_names = [v["name"] for v in config["tl_map"].values()]
    at_str = " ".join(f"@{name}" for name in tl_names)

    message = f"""【转介绍今日目标登记】
**团队类型：** {team}团队
**日期：** {date_str}（{weekday_str}）
**截止时间：** 今日 {deadline} 前

请登记今日目标（格式示例）：
| 小组 | 今日目标 | 小组进度目标 | 小组例子目标 | LP人均目标 |
|------|---------|------------|------------|-----------|
| {config['groups'][0]} | 50% | 20 | 2 |

{at_str} 请尽快登记"""

    if dry_run:
        print("\n[DRY-RUN] 将发送以下消息：")
        print(message)
    else:
        from dingtalk import send_markdown
        chatid = config["chatid"]
        if not chatid:
            print("  钉钉chatid未配置，跳过发送")
            print("\n[预览消息]：")
            print(message)
            return
        at_userids = [v["userid"] for v in config["tl_map"].values() if v["userid"]]
        send_markdown(chatid, "转介绍今日目标登记", message, at_users=at_userids)
        print("  发送成功")


def run_phase2(team, output_dir=None, dry_run=False):
    """阶段2：业绩进度播报"""
    print(f"\n{'='*50}")
    print(f"[阶段2] 业绩进度播报 — {team}团队")
    print(f"{'='*50}")

    output_dir = Path(output_dir or OUTPUT_DIR)

    # 1. 下载BI报表
    from bi_download import download_progress_report
    filepath = download_progress_report(output_dir)
    if not filepath:
        print("  BI报表下载失败，终止阶段2")
        return

    # 2. 读取数据（多级表头：第3-4行）
    import pandas as pd
    df = pd.read_excel(filepath, header=[3, 4])
    print(f"  读取数据: {len(df)} 行")

    # 3. 读取TL登记的今日目标（从钉钉多维表格）
    targets = _read_daily_targets(team)

    # 4. 计算进度和GAP
    config = TEAM_CONFIG[team]
    results = _compute_progress(df, config, targets)

    # 5. 标记落后对象（今日达标率 < 80%）
    lagging = [r for r in results if r["today_completion_rate"] < PROGRESS_THRESHOLD]

    # 6. 生成图片
    from render_image import render_progress_table
    image_path = render_progress_table(results, lagging, team)
    print(f"  生成图片: {image_path}")

    if dry_run:
        print("\n[DRY-RUN] 将发送图片消息")
        print(f"  图片路径: {image_path}")
        # 同时输出文本版本供参考
        message = _format_progress_report(team, results, lagging)
        print("\n[文本版本]：")
        print(message)
    else:
        from dingtalk import send_image, upload_media
        chatid = config["chatid"]
        if not chatid:
            print("  钉钉chatid未配置，跳过发送")
            print(f"  图片已保存: {image_path}")
            return

        # 上传图片并发送
        media_id = upload_media(image_path)
        send_image(chatid, media_id)
        print("  发送成功")


def run_phase3(team, output_dir=None, dry_run=False):
    """阶段3：外呼跟进预警"""
    print(f"\n{'='*50}")
    print(f"[阶段3] 外呼跟进预警 — {team}团队")
    print(f"{'='*50}")

    output_dir = Path(output_dir or OUTPUT_DIR)

    # 1. 下载BI报表
    from bi_download import download_followup_report
    filepath = download_followup_report(output_dir)
    if not filepath:
        print("  BI报表下载失败，终止阶段3")
        return

    # 2. 读取数据（传递文件路径用于后续处理）
    import pandas as pd
    df = pd.read_excel(filepath, header=[3, 4])
    # 将文件路径存储到df的attrs中，供_compute_followup使用
    df.attrs['filepath'] = filepath
    print(f"  读取数据: {len(df)} 行")

    # 3. 按池子分组计算
    config = TEAM_CONFIG[team]
    pool_results = _compute_followup(df, config)

    # 4. 生成图片
    from render_image import render_followup_warning
    image_path = render_followup_warning(pool_results, team)
    print(f"  生成图片: {image_path}")

    if dry_run:
        print("\n[DRY-RUN] 将发送图片消息")
        print(f"  图片路径: {image_path}")
    else:
        from dingtalk import send_image, upload_media
        chatid = config["chatid"]
        if not chatid:
            print("  钉钉chatid未配置，跳过发送")
            print(f"  图片已保存: {image_path}")
            return

        # 上传图片并发送
        media_id = upload_media(image_path)
        send_image(chatid, media_id)
        print("  发送成功")


def _read_daily_targets(team):
    """从钉钉多维表格读取TL登记的今日目标"""
    from config import DINGTALK_TABLE_ID, DINGTALK_TABLE_SHEET
    if not DINGTALK_TABLE_ID:
        print("  [WARN] 钉钉多维表格ID未配置，使用空目标")
        return {}
    try:
        from dingtalk import read_multidimensional_table
        return read_multidimensional_table(DINGTALK_TABLE_ID, DINGTALK_TABLE_SHEET)
    except Exception as e:
        print(f"  [WARN] 读取多维表格失败: {e}，使用空目标")
        return {}


def _compute_progress(df, config, targets):
    """计算每个小组+TL的进度和GAP"""
    results = []
    groups = config["groups"]

    for _, row in df.iterrows():
        # 多级列名访问：('团队/小组', 'Unnamed: 2_level_1')
        group = str(row[('团队/小组', row.index[2][1])]).strip()
        if group not in groups:
            continue

        # 只处理"总计"行（小组汇总数据）
        lp_col = ('LP', row.index[3][1])
        if str(row[lp_col]).strip() != '总计':
            continue

        tl = str(row[('负责人', row.index[4][1])]).strip()
        today_count = float(row[('今日完成情况', '今日例子数')] or 0)
        monthly_target = float(row[('海外转介绍例子数据', '海外转介绍例子目标')] or 0)
        total_count = float(row[('海外转介绍例子数据', '全体带海外例子数')] or 0)

        # 月度小组进度目标：优先取TL登记值；未登记则用自然日进度（今日/当月天数）
        group_progress_target = None
        today_target = 0

        if targets and group in targets:
            registered = targets[group].get("小组进度目标")
            if registered not in (None, "", 0):
                group_progress_target = float(registered)
            today_target = float(targets[group].get("小组例子目标", 0) or 0)

        if group_progress_target is None:
            today = datetime.now()
            days_in_month = calendar.monthrange(today.year, today.month)[1]
            group_progress_target = today.day / days_in_month

        # 如果TL没有填写今日目标，从BI报表读取作为fallback
        if today_target == 0:
            today_target = float(row[('今日完成情况', '今日例子目标')] or 0)

        # 今日达标率 = 今日例子数 / 今日例子目标
        today_completion_rate = today_count / today_target if today_target > 0 else 0

        # 例子达成率-月度 = 全体带海外例子数 / 海外转介绍例子目标
        monthly_completion_rate = total_count / monthly_target if monthly_target > 0 else 0

        # GAP例子量 = roundup(小组进度目标% × 海外转介绍例子目标 - 全体带海外例子数)
        gap_raw = group_progress_target * monthly_target - total_count
        gap = math.ceil(gap_raw) if gap_raw > 0 else 0

        results.append({
            "group": group,
            "tl": tl,
            "today_count": today_count,
            "today_target": today_target,
            "today_completion_rate": today_completion_rate,
            "monthly_target": monthly_target,
            "total_count": total_count,
            "monthly_completion_rate": monthly_completion_rate,
            "gap": gap,
        })

    return results


def _format_progress_report(team, results, lagging):
    """生成业绩播报markdown消息（已废弃，改用图片）"""
    today = datetime.now()
    lines = [
        f"📊 【转介绍业绩进度播报】",
        f"",
        f"| 小组 | 负责人 | 今日例子数 | 今日例子目标 | 今日达标率 | 海外转介绍例子目标 | 全体带海外例子数 | 例子达成率-月度 | GAP例子量 |",
        f"|------|--------|-----------|-------------|----------|------------------|----------------|---------------|---------|",
    ]

    for r in results:
        today_rate_str = f"{r['today_completion_rate']:.2%}"
        monthly_rate_str = f"{r['monthly_completion_rate']:.2%}"
        flag = "🔴 " if r["today_completion_rate"] < PROGRESS_THRESHOLD else ""
        lines.append(
            f"| {flag}{r['group']} | {r['tl']} | {r['today_count']:.0f} "
            f"| {r['today_target']:.0f} | {today_rate_str} | {r['monthly_target']:.0f} "
            f"| {r['total_count']:.0f} | {monthly_rate_str} | {r['gap']} |"
        )

    if lagging:
        lines.append("")
        lines.append("以下小组今日达标率不足80%，请对应TL关注：")
        for r in lagging:
            lines.append(
                f"🔴 {r['group']}（TL {r['tl']}）：今日达标率 {r['today_completion_rate']:.2%}，GAP {r['gap']}个"
            )

    return "\n".join(lines)


def _compute_followup(df, config):
    """按池子分组计算外呼跟进率

    从原始Excel读取，表头在第3-4行（索引2-3）
    池子数据分布：
    - 续费带R: 列22开始
    - M1-M3（首消）: 列50开始
    - 服务池: 列112开始
    """
    import pandas as pd

    # 重新读取原始数据，不使用多级表头
    filepath = df.attrs.get('filepath') if hasattr(df, 'attrs') else None
    if not filepath:
        # 从全局变量或其他方式获取文件路径
        from pathlib import Path
        filepath = Path(OUTPUT_DIR) / "外呼跟进_监控.xlsx"

    df_raw = pd.read_excel(filepath, header=None)

    # 池子配置：(池子名, 起始列索引)
    pool_configs = [
        ("续费带R", 22),
        ("M1-M3（首消）", 50),
        ("服务池", 112),
    ]

    results = {}
    groups = config["groups"]

    for pool_name, start_col in pool_configs:
        pool_results = []
        seen_groups = set()  # 记录已处理的小组，避免重复

        # 提取该池子的列索引
        # 学员数, 外呼跟进率, 外呼有效跟进率, 综合有效跟进率, 生均外呼次数, 带R数, 带R效率, 秒挂占比
        col_student = start_col
        col_call_rate = start_col + 1
        col_effective_rate = start_col + 2
        col_comprehensive_rate = start_col + 6
        col_avg_calls = start_col + 9
        col_带R数 = start_col + (10 if pool_name == "续费带R" else 10)
        col_带R效率 = start_col + (12 if pool_name == "续费带R" else 11)
        col_秒挂 = start_col + (13 if pool_name == "续费带R" else 12)

        # 遍历小组（从第4行开始，索引3）
        for row_idx in range(4, len(df_raw)):
            group_name = df_raw.iloc[row_idx, 1]  # 列1是小组名

            if pd.isna(group_name) or group_name not in groups:
                continue

            # 跳过已处理的小组
            if group_name in seen_groups:
                continue
            seen_groups.add(group_name)

            # 提取数据
            student_count = df_raw.iloc[row_idx, col_student]
            call_rate = df_raw.iloc[row_idx, col_call_rate]
            effective_rate = df_raw.iloc[row_idx, col_effective_rate]
            comprehensive_rate = df_raw.iloc[row_idx, col_comprehensive_rate]
            avg_calls = df_raw.iloc[row_idx, col_avg_calls]
            带R数 = df_raw.iloc[row_idx, col_带R数]
            带R效率 = df_raw.iloc[row_idx, col_带R效率]
            秒挂占比 = df_raw.iloc[row_idx, col_秒挂]

            # 转换为数值
            try:
                student_count = float(student_count) if pd.notna(student_count) else 0
                call_rate = float(call_rate) if pd.notna(call_rate) else 0
                effective_rate = float(effective_rate) if pd.notna(effective_rate) else 0
                comprehensive_rate = float(comprehensive_rate) if pd.notna(comprehensive_rate) else 0
                avg_calls = float(avg_calls) if pd.notna(avg_calls) else 0
                带R数 = int(float(带R数)) if pd.notna(带R数) else 0
                带R效率 = float(带R效率) if pd.notna(带R效率) else 0
                秒挂占比 = float(秒挂占比) if pd.notna(秒挂占比) else 0
            except (ValueError, TypeError):
                continue

            pool_results.append({
                "group": group_name,
                "student_count": student_count,
                "call_rate": call_rate,
                "effective_rate": effective_rate,
                "comprehensive_rate": comprehensive_rate,
                "avg_calls": avg_calls,
                "带R数": 带R数,
                "带R效率": 带R效率,
                "秒挂占比": 秒挂占比,
            })

        results[pool_name] = pool_results

    return results


def _format_followup_report(team, pool_results):
    """生成外呼跟进预警markdown消息"""
    lines = [
        "📞 【转介绍外呼做工预警】",
        "以下LP外呼做工不足，请对应TL跟进：",
        "",
    ]

    has_warning = False
    for pool, items in pool_results.items():
        lagging = [i for i in items if i["is_lagging"]]
        if not lagging:
            continue
        has_warning = True
        lines.append(f"**【{pool}】落后情况**")
        for item in lagging:
            lines.append(f"- {item['group']} | 外呼 {item['rate']:.0%} | 平均 {item['avg']:.0%} | 🔴")
        lines.append("")

    if not has_warning:
        lines.append("当前无落后小组，各组外呼做工正常。")

    config = TEAM_CONFIG[team]
    tl_names = [v["name"] for v in config["tl_map"].values()]
    lines.append("")
    lines.append(" ".join(f"@{name}" for name in tl_names))

    return "\n".join(lines)


def main():
    args = parse_args()

    if not check_schedule(args.team, args.phase, args.force):
        return

    if args.phase == "phase1":
        run_phase1(args.team, args.dry_run)
    elif args.phase == "phase2":
        run_phase2(args.team, args.output, args.dry_run)
    elif args.phase == "phase3":
        run_phase3(args.team, args.output, args.dry_run)
    elif args.phase == "all":
        run_phase1(args.team, args.dry_run)
        run_phase2(args.team, args.output, args.dry_run)
        run_phase3(args.team, args.output, args.dry_run)


if __name__ == "__main__":
    main()
