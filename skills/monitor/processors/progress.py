"""业绩进度数据处理器 — 参数化版本。"""
import pandas as pd
from pathlib import Path


class ProgressProcessor:
    """参数化的业绩进度计算器"""

    def __init__(self, phase_config):
        """
        Args:
            phase_config: phases.phase2 配置块
        """
        self.config = phase_config
        self.excel_cfg = phase_config["excel_parsing"]
        self.thresholds = phase_config["thresholds"]

    def compute_progress(self, excel_path, team_config, notable_targets):
        """计算业绩进度

        Args:
            excel_path: BI 导出的 Excel 文件路径
            team_config: 团队配置（groups, tl_map）
            notable_targets: Notable 读取的目标字典

        Returns:
            list[dict]: 小组维度的进度数据
        """
        df = pd.read_excel(
            excel_path,
            header=self.excel_cfg["header_rows"],
            engine="openpyxl",
        )

        cols = self.excel_cfg["columns"]
        results = []

        for group in team_config["groups"]:
            tl_info = team_config["tl_map"][group]
            tl_name = tl_info["name"]

            # 筛选该小组的 LP 行（排除 TL 自己和总计行）
            group_rows = df[df[tuple(cols["team_group"])] == group]
            lp_rows = []
            for _, row in group_rows.iterrows():
                lp_name = row[tuple(cols["lp"])]
                tl_name_in_row = row[tuple(cols["tl"])]
                # 排除 TL 行和总计行
                if lp_name == tl_name_in_row:
                    continue
                if pd.isna(lp_name) or lp_name == group:
                    continue
                lp_rows.append(row)

            if not lp_rows:
                continue

            # 汇总小组数据
            today_count = sum(row[tuple(cols["today_count"])] for row in lp_rows)
            total_count = sum(row[tuple(cols["total_count"])] for row in lp_rows)

            # 从 Notable 读取目标
            target_data = notable_targets.get(group, {})
            today_target = target_data.get("小组例子目标", 0)
            monthly_target_rate = target_data.get("小组进度目标", 0)

            # 计算月目标（基于当前总数和目标进度）
            if monthly_target_rate > 0:
                monthly_target = total_count / monthly_target_rate
            else:
                monthly_target = 0

            # 计算达标率
            today_completion_rate = today_count / today_target if today_target > 0 else 0
            monthly_completion_rate = total_count / monthly_target if monthly_target > 0 else 0

            # 计算 GAP（需要追赶的例子数）
            if monthly_target_rate > 0 and monthly_completion_rate < monthly_target_rate:
                gap = int((monthly_target_rate - monthly_completion_rate) * monthly_target)
            else:
                gap = 0

            results.append({
                "group": group,
                "tl": tl_name,
                "today_target": today_target,
                "today_count": today_count,
                "today_completion_rate": today_completion_rate,
                "monthly_target": monthly_target,
                "total_count": total_count,
                "monthly_completion_rate": monthly_completion_rate,
                "group_progress_target": monthly_target_rate,
                "gap": gap,
            })

        return results
