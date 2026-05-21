"""监控任务核心引擎 — phase 调度和执行。"""
from pathlib import Path
from datetime import datetime

from config_loader import load_config, get_secrets_loader
from datasources.smartbi import SmartbiDataSource
from datasources.notable import NotableDataSource
from processors.progress import ProgressProcessor
from processors.followup import FollowupProcessor
from renderers.table_image import TableRenderer
from notifiers.dingtalk import DingTalkNotifier


class MonitorEngine:
    """监控任务引擎"""

    def __init__(self, config_path):
        """
        Args:
            config_path: YAML 配置文件路径
        """
        self.config = load_config(config_path)
        self.secrets_loader = get_secrets_loader(self.config)
        self._init_datasources()
        self._init_notifier()

    def _init_datasources(self):
        """初始化数据源"""
        ds_cfg = self.config["datasources"]
        self.smartbi = SmartbiDataSource(ds_cfg["smartbi"], self.secrets_loader)
        self.notable = NotableDataSource(ds_cfg["notable"], self.secrets_loader)

    def _init_notifier(self):
        """初始化通知器"""
        notifier_cfg = self.config["notifier"]
        self.notifier = DingTalkNotifier(notifier_cfg, self.secrets_loader)

    def run_phase(self, team, phase_name):
        """运行指定团队的指定阶段

        Args:
            team: 团队名（如 '美澳' / '港澳'）
            phase_name: 阶段名（如 'phase1' / 'phase2' / 'phase3'）
        """
        team_cfg = self.config["teams"][team]
        phase_cfg = self.config["phases"][phase_name]
        phase_type = phase_cfg["type"]

        print(f"\n{'='*50}")
        print(f"[{phase_name}] {phase_cfg['description']} — {team}团队")
        print(f"{'='*50}")

        # 获取 chat_id
        secrets = self.secrets_loader()
        chat_id = secrets[team_cfg["chatid_key"]]

        if phase_type == "registration_reminder":
            self._run_registration_reminder(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "progress_monitor":
            self._run_progress_monitor(team, team_cfg, phase_cfg, chat_id)
        elif phase_type == "pool_warning":
            self._run_pool_warning(team, team_cfg, phase_cfg, chat_id)
        else:
            raise ValueError(f"未知的 phase 类型: {phase_type}")

    def _run_registration_reminder(self, team, team_cfg, phase_cfg, chat_id):
        """执行 TL 目标登记提醒"""
        tl_names = [info["name"] for info in team_cfg["tl_map"].values()]
        registered, unregistered = self.notable.get_registered_tls(team, tl_names)

        print(f"  [Notable API] 读取登记目标: {len(registered)} 个小组已登记")
        print(f"  已登记: {registered}")
        print(f"  未登记: {unregistered}")

        if not unregistered:
            print("  ✓ 所有 TL 已登记，无需提醒")
            return

        # 生成提醒消息
        table_url = self.notable.get_table_url()
        deadline = team_cfg["schedule"]["phase1_deadline"]
        message = phase_cfg["message_template"].format(
            team=team,
            unregistered_tls="、".join(unregistered),
            deadline=deadline,
            table_url=table_url,
        )

        # 发送
        self.notifier.send_markdown(chat_id, f"{team} 目标登记提醒", message)
        print("  发送成功")

    def _run_progress_monitor(self, team, team_cfg, phase_cfg, chat_id):
        """执行业绩进度监控"""
        output_dir = Path(self.config["globals"]["output_dir"]).expanduser()

        # 1. 下载 BI 报表
        report_name = phase_cfg["datasource"].split(".")[-1]  # "smartbi.progress" -> "progress"
        excel_path = self.smartbi.download_report(
            report_name,
            output_dir,
            self.config["_resolved"],
        )
        if not excel_path:
            print("  ✗ BI 报表下载失败")
            return

        # 2. 读取 Notable 目标
        notable_targets = self.notable.read_targets(team)
        print(f"  [Notable API] 读取到 {len(notable_targets)} 个小组目标")

        # 3. 计算进度
        processor = ProgressProcessor(phase_cfg)
        results = processor.compute_progress(excel_path, team_cfg, notable_targets)
        print(f"  计算完成: {len(results)} 个小组")

        # 4. 渲染表格
        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_progress_table(team, results)

        # 5. 发送
        self.notifier.send_image(chat_id, image_bytes.getvalue())
        print("  图片上传并发送成功")

    def _run_pool_warning(self, team, team_cfg, phase_cfg, chat_id):
        """执行外呼跟进预警"""
        output_dir = Path(self.config["globals"]["output_dir"]).expanduser()

        # 1. 下载 BI 报表
        report_name = phase_cfg["datasource"].split(".")[-1]  # "smartbi.followup" -> "followup"
        excel_path = self.smartbi.download_report(
            report_name,
            output_dir,
            self.config["_resolved"],
        )
        if not excel_path:
            print("  ✗ BI 报表下载失败")
            return

        # 2. 读取 Notable 目标
        notable_targets = self.notable.read_targets(team)

        # 3. 提取预警
        processor = FollowupProcessor(phase_cfg)
        warnings = processor.extract_warnings(excel_path, team_cfg, notable_targets)
        print(f"  提取预警: {len(warnings)} 个小组有未达标池子")

        if not warnings:
            print("  ✓ 所有池子达标，无需预警")
            return

        # 4. 渲染表格
        renderer = TableRenderer(phase_cfg["table_render"])
        image_bytes = renderer.render_followup_table(team, warnings)

        # 5. 发送
        self.notifier.send_image(chat_id, image_bytes.getvalue())
        print("  图片上传并发送成功")


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
