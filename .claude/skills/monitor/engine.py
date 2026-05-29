"""监控任务核心引擎 — phase 调度和执行。"""
import os
from pathlib import Path
from datetime import datetime

from config_loader import load_config, get_secrets_loader
from datasources.smartbi import SmartbiDataSource
from datasources.dingtalk_report import DingTalkReportDataSource
from processors.progress import ProgressProcessor
from processors.followup import FollowupProcessor
from processors.renewal import RenewalProcessor
from processors.service import ServiceProcessor
from renderers.table_image import TableRenderer
from notifiers.dingtalk import DingTalkNotifier


class MonitorEngine:
    """监控任务引擎"""

    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.secrets_loader = get_secrets_loader(self.config)
        self._init_datasources()
        self._init_notifier()

    def _init_datasources(self):
        """按需初始化数据源"""
        ds_cfg = self.config["datasources"]

        self.smartbi = None
        if "smartbi" in ds_cfg:
            self.smartbi = SmartbiDataSource(ds_cfg["smartbi"], self.secrets_loader)

        self.notable = None
        if "notable" in ds_cfg:
            from datasources.notable import NotableDataSource
            self.notable = NotableDataSource(ds_cfg["notable"], self.secrets_loader)

        self.dingtalk_report = None
        if "dingtalk_report" in ds_cfg:
            self.dingtalk_report = DingTalkReportDataSource(
                ds_cfg["dingtalk_report"], self.secrets_loader
            )

    def _target_required_fields(self):
        """当前场景用于判断是否已填写目标的核心字段。"""
        scenario = self.config.get("name", "").replace("_monitor", "")
        return {
            "intro": ["今日例子目标", "转介绍例子进度目标"],
            "renewal": ["续费目标"],
            "service": [
                "月度首通及时跟进目标",
                "月度首课及时跟进目标",
                "月度首专及时跟进目标",
            ],
        }.get(scenario, [])

    def _has_required_target(self, data):
        """至少一个核心目标字段非空非零，才允许执行该场景播报。"""
        if not data:
            return False
        for field in self._target_required_fields():
            val = data.get(field)
            if val not in (None, "", 0, 0.0):
                return True
        return False

    def _read_targets(self, team):
        """读取目标，自动适配 dingtalk_report 和 notable 的不同接口。

        美澳：先读钉钉日志，再用多维表格当日更新覆盖（小组级别）。
        港澳：直接读多维表格。
        """
        scenario = self.config.get("name", "").replace("_monitor", "")

        if team == "港澳":
            src = self.notable or self.dingtalk_report
            if src is self.notable:
                targets = src.read_targets(scenario, team=team)
            else:
                targets = src.read_targets(team)
            return {
                group: data
                for group, data in targets.items()
                if self._has_required_target(data)
            }

        # 美澳：日志为基础，多维表格今日更新覆盖
        base_targets = {}
        if self.dingtalk_report:
            base_targets = self.dingtalk_report.read_targets(team)

        if self.notable:
            notable_overrides = self.notable.read_targets(scenario, team="美澳", today_only=True)
            if notable_overrides:
                for group, data in notable_overrides.items():
                    print(f"  [多维表格覆盖] {group} 今日有更新，使用多维表格目标")
                base_targets.update(notable_overrides)

        return {
            group: data
            for group, data in base_targets.items()
            if self._has_required_target(data)
        }

    def _resolve_output_dir(self):
        """解析报表输出目录，优先使用环境变量覆盖。"""
        env_output_dir = os.environ.get("MONITOR_OUTPUT_DIR", "").strip()
        if env_output_dir:
            return Path(env_output_dir).expanduser()
        return Path(self.config["globals"]["output_dir"]).expanduser()
    def _init_notifier(self):
        notifier_cfg = self.config["notifier"]
        self.notifier = DingTalkNotifier(notifier_cfg, self.secrets_loader)

    def run_phase(self, team, phase_name):
        """运行指定团队的指定阶段"""
        team_cfg = self.config["teams"][team]
        phase_cfg = self.config["phases"][phase_name]
        phase_type = phase_cfg["type"]

        print(f"\n{'='*50}")
        print(f"[{phase_name}] {phase_cfg['description']} — {team}团队")
        print(f"{'='*50}")

        secrets = self.secrets_loader()
        chat_id = secrets[team_cfg["chatid_key"]]

        if phase_type == "registration_reminder":
            self._run_registration_reminder(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "progress_monitor":
            self._run_progress_monitor(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "pool_warning":
            self._run_pool_warning(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "renewal_monitor":
            self._run_renewal_monitor(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "service_monitor":
            self._run_service_monitor(team, team_cfg, phase_cfg, chat_id)
        else:
            raise ValueError(f"未知的 phase 类型: {phase_type}")

    def _run_registration_reminder(self, team, team_cfg, phase_cfg, chat_id):
        """执行 TL 目标登记/日志提交提醒"""
        tl_names = [info["name"] for info in team_cfg["tl_map"].values()]
        target_src = self._get_target_source(team)
        registered, unregistered = target_src.get_registered_tls(team, tl_names)

        print(f"  已提交: {registered}")
        print(f"  未提交: {unregistered}")

        if not unregistered:
            print("  ✓ 所有 TL 已提交，无需提醒")
            return

        deadline = team_cfg["schedule"].get("phase1_deadline", "10:00")
        message = phase_cfg["message_template"].format(
            team=team,
            unregistered_tls="、".join(unregistered),
            deadline=deadline,
        )

        self.notifier.send_markdown(chat_id, f"{team} 目标提醒", message)
        print("  发送成功")

    def _send_result(self, team_cfg, chat_id, image_bytes, title, alert_text,
                     at_userids=None, markdown_table=None):
        """路由发送：有 webhook_key 走 webhook（markdown 文字表格），否则走企业内部应用（图片+文字）"""
        webhook_key = team_cfg.get("webhook_key")
        if webhook_key:
            secrets = self.secrets_loader()
            webhook_url = secrets[webhook_key]
            at_mobiles = []
            if at_userids:
                for uid in at_userids:
                    for tl_info in team_cfg["tl_map"].values():
                        if str(tl_info.get("userid", "")) == str(uid):
                            mobile = tl_info.get("mobile")
                            if mobile:
                                at_mobiles.append(mobile)
                            break
            text = (markdown_table + "\n\n" + alert_text) if markdown_table else alert_text
            self.notifier.send_webhook_markdown(webhook_url, title, text,
                                                at_mobiles=at_mobiles or None)
        else:
            self.notifier.send_image_with_text(chat_id, image_bytes, title, alert_text,
                                               at_userids=at_userids or None)

    def _run_progress_monitor(self, team, team_cfg, phase_cfg, chat_id):
        """执行业绩进度监控"""
        output_dir = self._resolve_output_dir()

        report_name = phase_cfg["datasource"].split(".")[-1]
        excel_path = self.smartbi.download_report(
            report_name, output_dir, self.config["_resolved"],
        )
        if not excel_path:
            print("  ✗ BI 报表下载失败")
            return

        targets = self._read_targets(team)
        print(f"  读取到 {len(targets)} 个小组目标")
        if not targets:
            print("  未读取到当前场景的有效目标，跳过发送")
            return

        processor = ProgressProcessor(phase_cfg)
        results = processor.compute_progress(excel_path, team_cfg, targets)
        print(f"  计算完成: {len(results)} 个小组")
        if not results:
            print("  当前场景没有可播报小组，跳过发送")
            return

        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_progress_table(team, results)

        alert_text, at_userids = self._build_progress_alert_text(results, team_cfg)
        title = phase_cfg["table_render"]["title_template"].format(team=team)
        md_table = self._build_progress_markdown_table(results)
        # 把 markdown 表格插入预警文字的标题行之后
        full_text = alert_text.replace(
            "### 【小组今日目标达成情况】\n\n",
            f"### 【小组今日目标达成情况】\n\n{md_table}\n\n",
            1,
        )
        self._send_result(team_cfg, chat_id, image_bytes.getvalue(), title, full_text,
                          at_userids=at_userids or None)
        print("  发送成功")

    def _build_progress_alert_text(self, results, team_cfg=None):
        """构建进度预警文字

        格式：
        【小组今日目标达成情况】
        <markdown 表格>
        1、<小组汇总预警>
        2、以下LP今日例子进度为0且月进度未达成小组今日目标：
        各组LP明细
        """
        at_userids = []

        # 小组预警：今日达标率低于 100%
        today_lagging = [r for r in results if r.get("has_alert")]

        # @触发小组预警的TL
        for r in today_lagging:
            userid = ""
            if team_cfg:
                userid = team_cfg["tl_map"].get(r["group"], {}).get("userid", "")
            if userid and userid not in at_userids:
                at_userids.append(userid)

        # LP预警：今日=0 且月进度 < 小组目标，没有落后LP的小组不列出
        lp_lines = []
        for r in results:
            if not r.get("lagging_lps"):
                continue
            userid = ""
            if team_cfg:
                userid = team_cfg["tl_map"].get(r["group"], {}).get("userid", "")
            if userid and userid not in at_userids:
                at_userids.append(userid)
            lp_names = "、".join(lp["lp"] for lp in r["lagging_lps"])
            lp_lines.append(f"{r['group']}：{lp_names}")

        # 小组预警文字
        if not today_lagging:
            group_summary = "1、所有小组今日进度达标"
        else:
            lagging_names = "、".join(
                f"{r['group']}@{r['tl']}" for r in today_lagging
            )
            group_summary = f"1、各组均未达成目标，请查收各组GAP值，今日例子进度落后的小组：{lagging_names}"

        parts = ["### 【小组今日目标达成情况】", group_summary]
        if lp_lines:
            parts.append("2、以下LP今日例子进度为0且月进度未达成小组今日目标：\n\n" + "\n\n".join(lp_lines))
        return "\n\n".join(parts) + "\n\n", at_userids

    def _build_progress_markdown_table(self, results):
        """生成业绩进度 markdown 文字表格"""
        headers = ["小组", "TL", "今日目标", "今日例子", "今日达标率", "月目标", "月例子", "月进度", "GAP"]
        rows = []
        for r in results:
            today_rate_str = f"{r['today_completion_rate']:.0%}"
            if r["today_completion_rate"] < 1.0:
                today_rate_str = f"<font color=#FF0000>{today_rate_str}</font>"
            gap_val = r["gap"]
            gap_str = f"<font color=#FF0000>{gap_val}</font>" if gap_val > 0 else "-"
            rows.append([
                r["group"], r["tl"],
                f"{r['today_target']:.0f}", f"{r['today_count']:.0f}",
                today_rate_str,
                f"{r['monthly_target']:.0f}", f"{r['total_count']:.0f}",
                f"{r['monthly_completion_rate']:.0%}",
                gap_str,
            ])
        lines = ["| " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * len(headers)) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)

    def _run_pool_warning(self, team, team_cfg, phase_cfg, chat_id):
        """执行外呼跟进预警"""
        output_dir = self._resolve_output_dir()

        report_name = phase_cfg["datasource"].split(".")[-1]
        excel_path = self.smartbi.download_report(
            report_name, output_dir, self.config["_resolved"],
        )
        if not excel_path:
            print("  ✗ BI 报表下载失败")
            return

        targets = self._read_targets(team)

        processor = FollowupProcessor(phase_cfg)
        warnings = processor.extract_warnings(excel_path, team_cfg, targets)
        print(f"  提取预警: {len(warnings)} 个小组有未达标池子")

        if not warnings:
            print("  ✓ 所有池子达标，无需预警")
            return

        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_followup_table(team, warnings)

        alert_text, at_userids = self._build_followup_alert_text(team_cfg, warnings)
        title = phase_cfg["table_render"]["title_template"].format(team=team)
        md_table = self._build_followup_markdown_table(warnings)
        full_text = alert_text.replace(
            "### 【小组今日外呼跟进情况】\n\n",
            f"### 【小组今日外呼跟进情况】\n\n{md_table}\n\n",
            1,
        )
        self._send_result(team_cfg, chat_id, image_bytes.getvalue(), title, full_text,
                          at_userids=at_userids or None)
        print("  发送成功")

    def _build_followup_alert_text(self, team_cfg, warnings_per_group):
        """构建外呼跟进预警文字"""
        at_userids = []

        lagging_groups = list(warnings_per_group.keys())
        if not lagging_groups:
            group_summary = "1、所有小组今日外呼跟进达标"
        else:
            lagging_names = "、".join(
                f"{g}@{team_cfg['tl_map'].get(g, {}).get('name', g)}" for g in lagging_groups
            )
            group_summary = f"1、各组均未达成目标，请查收各组GAP值，今日外呼跟进落后的小组：{lagging_names}"

        lp_lines = []
        for group, items in warnings_per_group.items():
            tl_info = team_cfg["tl_map"].get(group, {})
            userid = tl_info.get("userid", "")
            if userid and userid not in at_userids:
                at_userids.append(userid)
            seen = set()
            lp_names = []
            for item in items:
                for lp in item.get("lagging_lps", []):
                    if lp["lp"] not in seen:
                        seen.add(lp["lp"])
                        lp_names.append(lp["lp"])
            if lp_names:
                lp_lines.append(f"{group}：{'、'.join(lp_names)}")

        parts = ["### 【小组今日外呼跟进情况】", group_summary]
        if lp_lines:
            parts.append("2、以下LP今日外呼跟进落后：\n\n" + "\n\n".join(lp_lines))
        return "\n\n".join(parts) + "\n\n", at_userids

    def _build_followup_markdown_table(self, warnings_per_group):
        """生成外呼跟进预警 markdown 文字表格"""
        headers = ["小组", "池子", "实际跟进率", "目标", "状态"]
        lines = ["| " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * len(headers)) + " |"]
        for group, items in warnings_per_group.items():
            for item in items:
                rate_str = f"{item['rate']:.0%}" if item["rate"] is not None else "-"
                lines.append(
                    f"| {group} | {item['pool']} | {rate_str} | {item['target']:.0%} | {item['status']} |"
                )
        return "\n".join(lines)

    def _run_renewal_monitor(self, team, team_cfg, phase_cfg, chat_id):
        """执行续费业绩预警"""
        output_dir = self._resolve_output_dir()

        excel_paths = {}
        reports_cfg = self.config["datasources"]["smartbi"]["reports"]
        for report_key in phase_cfg["excel_parsing"]:
            if report_key not in reports_cfg:
                continue
            path = self.smartbi.download_report(
                report_key, output_dir, self.config["_resolved"],
            )
            if path:
                excel_paths[report_key] = path
            else:
                print(f"  ✗ 报表 {report_key} 下载失败")

        if not excel_paths:
            print("  ✗ 无可用报表数据")
            return

        targets = self._read_targets(team)
        print(f"  读取到 {len(targets)} 个小组目标")

        processor = RenewalProcessor(phase_cfg)
        results = processor.evaluate_alerts(excel_paths, team_cfg, targets)
        alerted = [r for r in results if r["has_alert"]]
        print(f"  告警: {len(alerted)}/{len(results)} 个小组触发预警")

        if not results:
            print("  ✓ 无数据")
            return

        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_renewal_table(team, results)

        alert_text, at_userids = self._build_renewal_alert_text(results, alerted, team_cfg)
        title = phase_cfg["table_render"]["title_template"].format(team=team)
        md_table = self._build_renewal_markdown_table(results)
        full_text = alert_text.replace(
            "### 【小组今日续费情况】\n\n",
            f"### 【小组今日续费情况】\n\n{md_table}\n\n",
            1,
        )
        self._send_result(team_cfg, chat_id, image_bytes.getvalue(), title, full_text,
                          at_userids=at_userids or None)
        print("  发送成功")

    def _build_renewal_alert_text(self, results, alerted=None, team_cfg=None):
        """构建续费预警文字（@TL）
        results: 所有小组数据（用于汇总）
        alerted: 触发预警的小组（用于@人和详情）
        """
        if alerted is None:
            alerted = [r for r in results if r["has_alert"]]
        at_userids = []

        # @触发续费小组预警的TL
        for r in alerted:
            userid = r.get("userid", "")
            if not userid and team_cfg:
                userid = team_cfg["tl_map"].get(r["group"], {}).get("userid", "")
            if userid and userid not in at_userids:
                at_userids.append(userid)

        lagging_groups = [r["group"] for r in alerted]
        if not lagging_groups:
            group_summary = "1、所有小组今日续费达标"
        else:
            lagging_names = "、".join(
                f"{r['group']}@{r['tl']}" for r in alerted
            )
            group_summary = f"1、各组均未达成目标，请查收各组数据，今日续费预警的小组：{lagging_names}"

        lp_lines = []
        for r in alerted:
            detail_parts = []
            for alert in r["alerts"]:
                if alert == "续费未达标":
                    detail_parts.append(
                        f"续费GMV {r['renewal_gmv']:.0f}/目标 {r['renewal_target']:.0f}"
                        f"（差距 {r.get('renewal_gap', 0):.0f}）"
                    )
                elif alert == "低活跃":
                    detail_parts.append(
                        f"通时 {r['duration']:.0f}/{r['duration_target']:.0f}min、"
                        f"通次 {r['call_count']:.0f}/{r['count_target']:.0f}次"
                    )
                elif alert == "低跟进":
                    detail_parts.append(
                        f"外呼跟进率 {r['followup_rate']:.2%}/目标 {r['followup_target']:.2%}"
                        f"（差距 {r['followup_gap']:.2%}）"
                    )
            if detail_parts:
                lp_lines.append(f"{r['group']}：{'、'.join(detail_parts)}")

        # LP通时通次均为0的预警（遍历全部小组，不限于有小组预警的）
        lp_lagging_lines = []
        for r in results:
            if r.get("lagging_lps"):
                lp_names = "、".join(r["lagging_lps"])
                lp_lagging_lines.append(f"{r['group']}：{lp_names}")

        parts = ["### 【小组今日续费情况】", group_summary]
        if lp_lines:
            parts.append("2、以下小组续费指标预警，请对应TL跟进：\n\n" + "\n\n".join(lp_lines))
        if lp_lagging_lines:
            parts.append("3、以下LP通时通次均达成落后，请对应TL跟进：\n\n" + "\n\n".join(lp_lagging_lines))
        return "\n\n".join(parts) + "\n\n", at_userids

    def _build_renewal_markdown_table(self, results):
        """生成续费 markdown 文字表格（显示所有小组）"""
        headers = ["小组", "TL", "续费目标", "续费GMV", "通时目标", "通时", "通次目标", "通次", "跟进目标", "跟进率", "跟进GAP"]
        lines = ["| " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * len(headers)) + " |"]
        for r in results:
            followup_target = f"{r['followup_target']:.2%}" if r.get("followup_target") else "-"
            followup_rate = f"{r['followup_rate']:.2%}" if r.get("followup_target") else "-"
            followup_gap = f"{r['followup_gap']:.2%}" if r.get("followup_gap") else "-"
            lines.append(
                f"| {r['group']} | {r['tl']} "
                f"| {r['renewal_target']:.0f} | {r['renewal_gmv']:.0f} "
                f"| {r['duration_target']:.0f} | {r['duration']:.0f} "
                f"| {r['count_target']:.0f} | {r['call_count']:.0f} "
                f"| {followup_target} | {followup_rate} | {followup_gap} |"
            )
        return "\n".join(lines)

    def _run_service_monitor(self, team, team_cfg, phase_cfg, chat_id):
        """执行服务指标预警"""
        output_dir = self._resolve_output_dir()

        excel_paths = {}
        reports_cfg = self.config["datasources"]["smartbi"]["reports"]
        for report_key in phase_cfg["excel_parsing"]:
            if report_key not in reports_cfg:
                continue
            path = self.smartbi.download_report(
                report_key, output_dir, self.config["_resolved"],
            )
            if path:
                excel_paths[report_key] = path
            else:
                print(f"  ✗ 报表 {report_key} 下载失败")

        if not excel_paths:
            print("  ✗ 无可用报表数据")
            return

        targets = self._read_targets(team)
        print(f"  读取到 {len(targets)} 个小组目标")

        processor = ServiceProcessor(phase_cfg)
        results = processor.evaluate_alerts(excel_paths, team_cfg, targets)
        alerted = [r for r in results if r["has_alert"]]
        print(f"  告警: {len(alerted)}/{len(results)} 个小组触发预警")

        if not alerted:
            print("  ✓ 无预警")
            return

        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_service_table(team, alerted)

        alert_text, at_userids = self._build_service_alert_text(alerted, team_cfg)
        title = phase_cfg["table_render"]["title_template"].format(team=team)
        md_table = self._build_service_markdown_table(alerted)
        full_text = alert_text.replace(
            "### 【小组今日服务情况】\n\n",
            f"### 【小组今日服务情况】\n\n{md_table}\n\n",
            1,
        )
        self._send_result(team_cfg, chat_id, image_bytes.getvalue(), title, full_text,
                          at_userids=at_userids or None)
        print("  发送成功")

    def _build_service_alert_text(self, alerted, team_cfg=None):
        """构建服务预警文字（@TL）"""
        metric_labels = {
            "首通低于目标": ("first_call_rate", "first_call_target", "首通及时跟进率"),
            "首课低于目标": ("first_lesson_rate", "first_lesson_target", "首课及时跟进率"),
            "首专低于目标": ("first_specialist_rate", "first_specialist_target", "首专及时跟进率"),
            "服务池跟进低于目标": ("pool_followup_rate", "pool_followup_target", "服务池跟进率"),
            "有效跟进低于目标": ("pool_effective_rate", "pool_effective_target", "有效跟进率"),
        }
        at_userids = []

        lagging_groups = [r["group"] for r in alerted]
        if not lagging_groups:
            group_summary = "1、所有小组今日服务指标达标"
        else:
            lagging_names = "、".join(
                f"{r['group']}@{r['tl']}" for r in alerted
            )
            group_summary = f"1、各组均未达成目标，请查收各组数据，今日服务指标预警的小组：{lagging_names}"

        lp_lines = []
        for r in alerted:
            userid = r.get("userid", "")
            if not userid and team_cfg:
                userid = team_cfg["tl_map"].get(r["group"], {}).get("userid", "")
            if userid and userid not in at_userids:
                at_userids.append(userid)
            detail_parts = []
            for alert in r["alerts"]:
                if alert in metric_labels:
                    actual_key, target_key, label = metric_labels[alert]
                    actual = r.get(actual_key, 0)
                    target = r.get(target_key, 0)
                    detail_parts.append(f"{label} {actual:.0%}/目标 {target:.0%}（差距 {target - actual:.0%}）")
            if detail_parts:
                lp_lines.append(f"{r['group']}：{'、'.join(detail_parts)}")

        parts = ["### 【小组今日服务情况】", group_summary]
        if lp_lines:
            parts.append("2、以下小组服务指标预警，请对应TL跟进：\n\n" + "\n\n".join(lp_lines))
        return "\n\n".join(parts) + "\n\n", at_userids

    def _build_service_markdown_table(self, alerted):
        """生成服务指标预警 markdown 文字表格"""
        headers = ["小组", "TL", "首通目标", "首通率", "首课目标", "首课率", "首专目标", "首专率", "服务池目标", "服务池率", "有效跟进目标", "有效跟进率"]
        lines = ["| " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * len(headers)) + " |"]
        for r in alerted:
            lines.append(
                f"| {r['group']} | {r['tl']} "
                f"| {r['first_call_target']:.0%} | {r['first_call_rate']:.0%} "
                f"| {r['first_lesson_target']:.0%} | {r['first_lesson_rate']:.0%} "
                f"| {r['first_specialist_target']:.0%} | {r['first_specialist_rate']:.0%} "
                f"| {r['pool_followup_target']:.0%} | {r['pool_followup_rate']:.0%} "
                f"| {r['pool_effective_target']:.0%} | {r['pool_effective_rate']:.0%} |"
            )
        return "\n".join(lines)


def run_monitor(config_path, team, phase):
    """便捷入口函数

    Args:
        config_path: YAML 配置文件路径
        team: 团队名
        phase: 阶段名
    """
    engine = MonitorEngine(config_path)
    engine.run_phase(team, phase)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("用法: python engine.py <config.yaml> <team> <phase>")
        print("示例: python engine.py examples/weekly_intro_monitor.yaml 美澳 phase2")
        sys.exit(1)

    config_path = sys.argv[1]
    team = sys.argv[2]
    phase = sys.argv[3]

    run_monitor(config_path, team, phase)
