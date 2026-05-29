#!/usr/bin/env python3
"""监控调度入口 — 根据团队和时间自动路由到对应场景和 phase。

用法：
    python3 dispatch.py <team> <phase_type>

    team: 美澳 / 港澳
    phase_type: target_confirm / target_reminder / progress / followup
"""
import sys
from pathlib import Path
from config_loader import load_config, get_secrets_loader
from datasources.dingtalk_report import DingTalkReportDataSource
from datasources.notable import NotableDataSource
from notifiers.dingtalk import DingTalkNotifier
from renderers.table_image import TableRenderer


def _send_message(notifier, team_cfg, secrets, chat_id, title, markdown_text, at_groups=None):
    """发消息：有 webhook_key 的团队走 webhook + atMobiles，否则走企业内部应用"""
    webhook_key = team_cfg.get("webhook_key")
    if webhook_key:
        webhook_url = secrets[webhook_key]
        at_mobiles = []
        if at_groups:
            for g in at_groups:
                mobile = team_cfg["tl_map"].get(g, {}).get("mobile")
                if mobile:
                    at_mobiles.append(mobile)
        notifier.send_webhook_markdown(webhook_url, title, markdown_text, at_mobiles=at_mobiles or None)
    else:
        at_userids = []
        if at_groups:
            for g in at_groups:
                uid = team_cfg["tl_map"].get(g, {}).get("userid")
                if uid:
                    at_userids.append(str(uid))
        notifier.send_markdown(chat_id, title, markdown_text, at_userids=at_userids or None)


def _fmt_pct(val):
    """安全格式化百分比，失败返回原值字符串"""
    if val is None or val == "" or val == 0:
        return "-"
    try:
        return f"{float(val):.0%}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_num(val, suffix=""):
    """安全格式化数字"""
    if val is None or val == "" or val == 0:
        return "-"
    try:
        return f"{float(val):.0f}{suffix}"
    except (ValueError, TypeError):
        return str(val)


def _has_target_data(scenario, data):
    """判断日志数据中是否有该场景的实际目标值（非零非空）"""
    if not data:
        return False
    check_fields = {
        "intro":   ["今日例子目标", "转介绍例子进度目标", "外呼跟进目标"],
        "renewal": ["续费目标", "通时目标", "通次目标", "外呼跟进目标"],
        "service": ["月度首通及时跟进目标", "月度首课及时跟进目标", "月度首专及时跟进目标"],
    }
    for field in check_fields.get(scenario, []):
        val = data.get(field)
        if val and val != 0:
            return True
    return False


def run_target_confirm(team, config, date_str=None):
    """目标确认 — 港澳读多维表格，美澳读钉钉日志；展示已填目标，@未填TL提醒"""
    print(f"\n{'='*50}")
    print(f"[目标确认] {team}团队")
    print('='*50)

    secrets_loader = get_secrets_loader(config)
    team_cfg = config["teams"][team]
    notifier = DingTalkNotifier(config["notifier"], secrets_loader)
    chat_id = secrets_loader()[team_cfg["chatid_key"]]
    notable_cfg = config["datasources"]["notable"]

    scenario_name_map = {"intro": "转介绍", "renewal": "续费", "service": "服务"}
    headers_map = {
        "intro":   ["场景", "小组", "TL", "今日例子目标", "进度目标", "跟进池子", "外呼跟进目标"],
        "renewal": ["场景", "小组", "TL", "续费目标", "通时目标", "通次目标", "外呼跟进目标"],
        "service": ["场景", "小组", "TL", "首通目标", "首课目标", "首专目标"],
    }

    # Step 1: 确定活跃场景 + 读目标数据
    all_log_targets = {}  # {scenario: {group: {field: val}}}

    if team == "港澳":
        # 港澳：从多维表格读目标
        notable_src = NotableDataSource(notable_cfg, secrets_loader)
        active_scenarios = notable_src.get_active_scenarios(team="港澳")
        print(f"  多维表格活跃场景: {[scenario_name_map[s] for s in active_scenarios]}")
        for scenario in active_scenarios:
            all_log_targets[scenario] = notable_src.read_targets(scenario, team="港澳")
            print(f"  {scenario_name_map[scenario]} 多维表格: {len(all_log_targets[scenario])} 个小组有目标")
    else:
        # 美澳：从钉钉日志读节奏规划 + 目标
        base_ds_cfg = config["datasources"]["dingtalk_report"]
        base_src = DingTalkReportDataSource(base_ds_cfg, secrets_loader)
        schedule_result = base_src.read_schedule_and_targets(team, date_str=date_str)
        active_scenarios = schedule_result["scenarios"]
        print(f"  今日场景: {[scenario_name_map[s] for s in active_scenarios]}")
        for scenario in active_scenarios:
            cfg_file = f"generated/{scenario}_monitor.yaml"
            if not Path(cfg_file).exists():
                print(f"  ⚠ 配置文件不存在: {cfg_file}")
                all_log_targets[scenario] = {}
                continue
            scenario_cfg = load_config(cfg_file)
            scenario_src = DingTalkReportDataSource(scenario_cfg["datasources"]["dingtalk_report"], secrets_loader)
            all_log_targets[scenario] = scenario_src.read_targets(team, date_str=date_str)
            print(f"  {scenario_name_map[scenario]} 日志: {len(all_log_targets[scenario])} 个小组有目标")

    if not active_scenarios:
        print("  未检测到活跃场景，发送多维表格填写提醒")
        table_url = notable_cfg.get("table_url", "")
        all_groups = team_cfg["groups"]
        lines = [f"**【{team}团队今日目标登记提醒】**\n", "请各位 TL 登记今日小组目标：\n"]
        for g in all_groups:
            tl_name = team_cfg["tl_map"][g]["name"]
            lines.append(f"- @{tl_name}（{g}）")
        if table_url:
            lines.append(f"\n填写链接：{table_url}")
        _send_message(
            notifier, team_cfg, secrets_loader(), chat_id,
            f"{team}团队目标登记提醒", "\n".join(lines),
            at_groups=all_groups,
        )
        print(f"  ✓ 提醒已发送（@{len(all_groups)} 个TL）")
        return

    # Step 3: 判断每个 TL 在哪些场景填了日志
    # group → set of scenarios with data
    group_filled_scenarios = {g: set() for g in team_cfg["groups"]}
    for scenario, targets in all_log_targets.items():
        for group, data in targets.items():
            if group in group_filled_scenarios and _has_target_data(scenario, data):
                group_filled_scenarios[group].add(scenario)

    # Step 4: 按场景发送目标确认图（只含有日志数据的组）
    sent_any = False
    for scenario in active_scenarios:
        targets = all_log_targets.get(scenario, {})
        filled_groups = [g for g in team_cfg["groups"] if scenario in group_filled_scenarios[g]]
        if not filled_groups:
            print(f"  {scenario_name_map[scenario]}: 无组填写日志，跳过")
            continue

        scenario_label = scenario_name_map[scenario]
        headers = headers_map[scenario]
        rows = []
        for group in filled_groups:
            tl_name = team_cfg["tl_map"][group]["name"]
            d = targets.get(group, {})
            if scenario == "intro":
                pools = d.get("跟进池子", [])
                pools_str = "、".join(pools) if isinstance(pools, list) else str(pools or "-")
                rows.append([
                    scenario_label, group, tl_name,
                    _fmt_num(d.get("今日例子目标")),
                    _fmt_pct(d.get("转介绍例子进度目标")),
                    pools_str or "-",
                    _fmt_pct(d.get("外呼跟进目标")),
                ])
            elif scenario == "renewal":
                rows.append([
                    scenario_label, group, tl_name,
                    _fmt_num(d.get("续费目标")),
                    _fmt_num(d.get("通时目标"), "min"),
                    _fmt_num(d.get("通次目标"), "次"),
                    _fmt_pct(d.get("外呼跟进目标")),
                ])
            elif scenario == "service":
                rows.append([
                    scenario_label, group, tl_name,
                    _fmt_pct(d.get("月度首通及时跟进目标")),
                    _fmt_pct(d.get("月度首课及时跟进目标")),
                    _fmt_pct(d.get("月度首专及时跟进目标")),
                ])

        # 已填写的 TL @确认
        at_userids = [
            team_cfg["tl_map"][g]["userid"]
            for g in filled_groups
            if team_cfg["tl_map"][g].get("userid")
        ]

        # 未填写该场景的组列表（用于图片下方文字）
        unfilled_in_scenario = [g for g in team_cfg["groups"] if scenario not in group_filled_scenarios[g]]

        if team == "港澳":
            confirm_lines = ["以上为各组今日目标，请各 TL 确认目标，如有误请及时更正在多维表格\n"]
        else:
            confirm_lines = ["以上为各组今日目标（日志读取），请各 TL 确认目标，如有误请及时更正在多维表格\n"]
        for group in filled_groups:
            tl_name = team_cfg["tl_map"][group]["name"]
            confirm_lines.append(f"- **{group}（@{tl_name}）** ✅ 已填写")
        for group in unfilled_in_scenario:
            tl_name = team_cfg["tl_map"][group]["name"]
            confirm_lines.append(f"- **{group}（@{tl_name}）** ⚠️ 未填写")
        confirm_text = "\n".join(confirm_lines)

        title = f"【{scenario_label}目标确认 — {team}团队】"
        renderer = TableRenderer({"title_template": title, "headers": headers, "color_rules": []})
        image_bytes = renderer.render_simple_table(title, headers, rows)

        webhook_key = team_cfg.get("webhook_key")
        if webhook_key:
            # webhook 不支持图片，改用 markdown 文字表格
            md_rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
            for row in rows:
                md_rows.append("| " + " | ".join(str(c) for c in row) + " |")
            full_text = f"{title}\n\n" + "\n".join(md_rows) + "\n\n" + confirm_text
            _send_message(
                notifier, team_cfg, secrets_loader(), chat_id,
                title, full_text, at_groups=filled_groups,
            )
        else:
            notifier.send_image_with_text(
                chat_id, image_bytes.getvalue(), title, confirm_text,
                at_userids=[str(team_cfg["tl_map"][g]["userid"]) for g in filled_groups if team_cfg["tl_map"][g].get("userid")] or None,
            )
        print(f"  ✓ {scenario_label}目标确认已发送（{len(filled_groups)} 组，@{len(filled_groups)} 个TL）")
        sent_any = True

    # Step 5: 全场景均未填日志的 TL → @提醒去多维表格
    fully_unfilled = [
        g for g in team_cfg["groups"]
        if not group_filled_scenarios[g]
    ]
    if fully_unfilled:
        table_url = notable_cfg.get("table_url", "")
        lines = ["**以下TL尚未登记今日目标，请尽快登记在多维表格**\n"]
        for group in fully_unfilled:
            tl_name = team_cfg["tl_map"][group]["name"]
            lines.append(f"- @{tl_name}（{group}）")
        if table_url:
            lines.append(f"\n填写链接：{table_url}")
        _send_message(
            notifier, team_cfg, secrets_loader(), chat_id,
            f"{team}团队目标未登记提醒", "\n".join(lines),
            at_groups=fully_unfilled,
        )
        print(f"  ✓ 未登记提醒已发送（@{'、'.join(team_cfg['tl_map'][g]['name'] for g in fully_unfilled)}）")

    if not sent_any and not fully_unfilled:
        print("  今日无任何日志数据")


def run_target_reminder(team, config):
    """港澳目标提醒 — 发多维表格链接 @TL"""
    print(f"\n{'='*50}")
    print(f"[目标提醒] {team}团队")
    print('='*50)

    secrets_loader = get_secrets_loader(config)
    notable_cfg = config["datasources"]["notable"]
    notifier_cfg = config["notifier"]

    notifier = DingTalkNotifier(notifier_cfg, secrets_loader)
    team_cfg = config["teams"][team]
    chat_id = secrets_loader()[team_cfg["chatid_key"]]

    table_url = notable_cfg["table_url"]
    tl_names = [info["name"] for info in team_cfg["tl_map"].values()]

    message = f"""**【{team}团队每日目标登记提醒】**

请各位 TL 点击下方链接打开多维表格，登记今日小组目标：

{table_url}

@{" @".join(tl_names)}"""

    all_groups = list(team_cfg["tl_map"].keys())
    _send_message(
        notifier, team_cfg, secrets_loader(), chat_id,
        f"{team}团队每日目标登记提醒", message,
        at_groups=all_groups,
    )
    print("  ✓ 多维表格链接已发送")


def run_progress_or_followup(team, phase_type, config):
    """动态路由 — 根据数据源决定跑哪些场景的 phase2 / phase3 / 两者合并"""
    print(f"\n{'='*50}")
    print(f"[{phase_type}] {team}团队 — 动态路由")
    print('='*50)

    secrets_loader = get_secrets_loader(config)

    # 美澳：读日志节奏规划，再验证各场景是否真的有目标数据
    if team == "美澳":
        ds_cfg = config["datasources"]["dingtalk_report"]
        report_src = DingTalkReportDataSource(ds_cfg, secrets_loader)
        result = report_src.read_schedule_and_targets(team)
        schedule_scenarios = result["scenarios"]
        print(f"  美澳节奏规划: {schedule_scenarios}")

        # 验证：只保留真正有目标数据的场景（用 _has_target_data 检查实质字段）
        scenarios = []
        for scenario in schedule_scenarios:
            cfg_file = f"generated/{scenario}_monitor.yaml"
            if not Path(cfg_file).exists():
                continue
            scenario_cfg = load_config(cfg_file)
            scenario_src = DingTalkReportDataSource(
                scenario_cfg["datasources"]["dingtalk_report"], secrets_loader
            )
            targets = scenario_src.read_targets(team)
            has_real_data = any(_has_target_data(scenario, d) for d in targets.values())
            if has_real_data:
                scenarios.append(scenario)
                print(f"  ✓ {scenario}: {len(targets)} 个小组有目标")
            else:
                print(f"  ✗ {scenario}: 无实质目标数据，跳过")

    # 港澳：读多维表格 sheet
    else:
        notable_cfg = config["datasources"]["notable"]
        notable_src = NotableDataSource(notable_cfg, secrets_loader)
        scenarios = notable_src.get_active_scenarios(team="港澳")
        print(f"  港澳活跃 sheet: {scenarios}")

    if not scenarios:
        print("  未检测到活跃场景，跳过")
        return

    from engine import MonitorEngine

    # phase_type: progress=只跑phase2, followup=只跑phase3, monitor=phase2+phase3
    if phase_type == "progress":
        phases_to_run = ["phase2"]
    elif phase_type == "followup":
        phases_to_run = ["phase3"]
    else:  # monitor
        phases_to_run = ["phase2", "phase3"]

    for scenario in scenarios:
        config_file = f"generated/{scenario}_monitor.yaml"
        if not Path(config_file).exists():
            print(f"  ⚠ 配置文件不存在: {config_file}")
            continue

        scenario_cfg = load_config(config_file)
        for phase in phases_to_run:
            if phase not in scenario_cfg.get("phases", {}):
                print(f"  → {scenario} 无 {phase}，跳过")
                continue
            print(f"\n  → 执行 {scenario} {phase}")
            engine = MonitorEngine(config_file)
            engine.run_phase(team, phase)


def clear_notable_targets(config):
    """每天 23:00 清空多维表格所有 sheet 的目标字段，保留小组和负责人"""
    print(f"\n{'='*50}")
    print("[清空多维表格] 清除今日目标数据")
    print('='*50)

    secrets_loader = get_secrets_loader(config)
    notable_cfg = config["datasources"]["notable"]
    src = NotableDataSource(notable_cfg, secrets_loader)

    token = src._get_access_token()
    union_id = src._get_union_id(token)
    base_id = notable_cfg["base_id"]

    # 各 sheet 需要清空的字段（多选字段用 []，文本/数字字段用 ''）
    sheet_clear_fields = {
        "QbhH3co": {  # 转介绍日监控
            "转介绍例子进度目标": "", "外呼跟进目标": "", "今日例子目标": "",
            "跟进池子": [],  # 多选字段
        },
        "QL7ScLh": {  # 续费日监控
            "外呼跟进目标": "", "续费目标": "", "通时目标": "", "通次目标": "",
        },
        "v3b5TrR": {  # 服务监控
            "首通及时跟进目标": "", "首课及时跟进目标": "", "首专及时跟进目标": "",
            "服务池外呼跟进目标": "", "服务池有效跟进目标": "",
        },
    }

    import requests
    for sheet_id, clear_fields in sheet_clear_fields.items():
        resp = requests.get(
            f"https://api.dingtalk.com/v1.0/notable/bases/{base_id}/sheets/{sheet_id}/records",
            headers={"x-acs-dingtalk-access-token": token},
            params={"operatorId": union_id, "maxResults": 100},
            timeout=15,
        )
        records = resp.json().get("records", [])
        if not records:
            continue

        updates = []
        for rec in records:
            rec_id = rec.get("id")
            if not rec_id:
                continue
            existing_fields = rec.get("fields", {})
            # 只清空实际存在值的字段，避免 API 报错
            fields_to_clear = {
                k: v for k, v in clear_fields.items()
                if k in existing_fields and existing_fields[k] not in (None, "", [])
            }
            if fields_to_clear:
                updates.append({"id": rec_id, "fields": fields_to_clear})

        if not updates:
            print(f"  ✓ sheet {sheet_id}: 无需清空")
            continue

        r = requests.put(
            f"https://api.dingtalk.com/v1.0/notable/bases/{base_id}/sheets/{sheet_id}/records",
            headers={"x-acs-dingtalk-access-token": token, "Content-Type": "application/json"},
            json={"operatorId": union_id, "records": updates},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  ✓ sheet {sheet_id}: 清空 {len(updates)} 条记录")
        else:
            print(f"  ✗ sheet {sheet_id}: 清空失败 {r.status_code} {r.text[:150]}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 dispatch.py <team|clear> [phase_type] [--date YYYY-MM-DD]")
        print("  team: 美澳 / 港澳")
        print("  phase_type:")
        print("    target_confirm  — 9:00美澳 / 12:00港澳")
        print("    progress        — 11:30美澳（仅phase2）")
        print("    monitor         — 14:30/17:00美澳，14:00/17:30/19:00港澳（phase2+phase3）")
        print("  clear             — 23:00 清空多维表格今日目标")
        sys.exit(1)

    # 解析可选 --date 参数
    date_override = None
    args = sys.argv[1:]
    if "--date" in args:
        idx = args.index("--date")
        if idx + 1 < len(args):
            date_override = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    first_arg = args[0] if args else ""

    # 加载基础配置
    config = load_config("generated/intro_monitor.yaml")

    if first_arg == "clear":
        clear_notable_targets(config)
        return

    if len(args) < 2:
        print("用法: python3 dispatch.py <team> <phase_type>")
        sys.exit(1)

    team = first_arg
    phase_type = args[1]

    if phase_type == "target_confirm":
        run_target_confirm(team, config, date_str=date_override)
    elif phase_type == "target_reminder":
        run_target_reminder(team, config)
    elif phase_type in ["progress", "followup", "monitor"]:
        run_progress_or_followup(team, phase_type, config)
    else:
        print(f"未知 phase_type: {phase_type}")
        sys.exit(1)


if __name__ == "__main__":
    main()
