"""外呼跟进数据处理器 — 参数化版本。"""
import pandas as pd


class FollowupProcessor:
    """参数化的外呼跟进预警处理器"""

    def __init__(self, phase_config):
        """
        Args:
            phase_config: phases.phase3 配置块
        """
        self.config = phase_config
        self.pool_configs = phase_config["pool_configs"]
        self.thresholds = phase_config["thresholds"]

    def extract_warnings(self, excel_path, team_config, notable_targets):
        """提取外呼跟进预警

        Args:
            excel_path: BI 导出的 Excel 文件路径
            team_config: 团队配置
            notable_targets: Notable 读取的目标字典

        Returns:
            dict: {小组名: [{pool, rate, target, status, gap}, ...]}
        """
        df = pd.read_excel(excel_path, header=1, engine="openpyxl")

        warnings_per_group = {}

        for group in team_config["groups"]:
            target_data = notable_targets.get(group, {})
            monitored_pools = target_data.get("跟进池子", [])
            if not monitored_pools:
                continue

            group_warnings = []

            for pool_cfg in self.pool_configs:
                pool_name = pool_cfg["name"]
                if pool_name not in monitored_pools:
                    continue

                col_offset = pool_cfg["column_offset"]
                target = pool_cfg.get("target", self.thresholds["call_low"])

                # 读取该池子的跟进率
                try:
                    group_row = df[df.iloc[:, 0] == group]
                    if group_row.empty:
                        continue
                    rate_value = group_row.iloc[0, col_offset]
                    if pd.isna(rate_value):
                        rate = None
                    else:
                        rate = float(rate_value)
                except (IndexError, ValueError):
                    rate = None

                # 判断状态
                if rate is None:
                    status = "无数据"
                    gap = None
                elif rate < target:
                    status = "未达标"
                    gap = target - rate
                else:
                    status = "达标"
                    gap = None

                if status != "达标":
                    group_warnings.append({
                        "pool": pool_name,
                        "rate": rate,
                        "target": target,
                        "status": status,
                        "gap": gap,
                    })

            if group_warnings:
                warnings_per_group[group] = group_warnings

        return warnings_per_group
