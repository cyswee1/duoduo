"""业绩进度数据处理器 — 参数化版本。"""
import pandas as pd
from pathlib import Path


class ProgressProcessor:
    """参数化的业绩进度计算器"""

    def __init__(self, phase_config):
        self.config = phase_config
        self.excel_cfg = phase_config["excel_parsing"]
        self.thresholds = phase_config["thresholds"]

    def compute_progress(self, excel_path, team_config, notable_targets):
        """计算业绩进度，返回小组维度数据（含 LP 明细）"""
        df = pd.read_excel(
            excel_path,
            header=self.excel_cfg["header_rows"],
            engine="openpyxl",
        )

        cols = self.excel_cfg["columns"]
        # 合并格：团队/小组列只有首行有值，其余为 NaN，需要向下填充
        df[tuple(cols["team_group"])] = df[tuple(cols["team_group"])].ffill()
        results = []

        for group in team_config["groups"]:
            tl_info = team_config["tl_map"][group]
            tl_name = tl_info["name"]

            group_rows = df[df[tuple(cols["team_group"])] == group]

            # 总计行：取小组汇总数据（今日例子、月累计、月目标）
            monthly_target_bi = 0
            today_count = 0
            total_count = 0
            summary_rows = group_rows[group_rows[tuple(cols["lp"])] == "总计"]
            if not summary_rows.empty:
                sr = summary_rows.iloc[0]
                monthly_target_bi = self._safe_float(sr[tuple(cols["monthly_target"])])
                today_count = self._safe_float(sr[tuple(cols["today_count"])])
                total_count = self._safe_float(sr[tuple(cols["total_count"])])

            lp_rows = []
            for _, row in group_rows.iterrows():
                lp_name = row[tuple(cols["lp"])]
                if lp_name == "总计":
                    continue
                if pd.isna(lp_name) or lp_name == group:
                    continue
                if lp_name == tl_name:
                    continue
                lp_rows.append(row)

            if not lp_rows:
                continue

            target_data = notable_targets.get(group, {})
            if not target_data:
                continue
            today_target_log = self._safe_float(target_data.get("今日例子目标", 0))
            monthly_target_val = self._safe_float(target_data.get("转介绍例子进度目标", 0))

            monthly_target = monthly_target_bi if monthly_target_bi > 0 else 0
            today_target_bi = 0
            if not summary_rows.empty and "today_target" in cols:
                today_target_bi = self._safe_float(sr[tuple(cols["today_target"])])
            today_target = today_target_log if today_target_log > 0 else today_target_bi

            today_completion_rate = today_count / today_target if today_target > 0 else 0
            monthly_completion_rate = total_count / monthly_target if monthly_target > 0 else 0

            # 月进度目标（TL 日志填的，如 0.6）
            group_progress_target = monthly_target_val if monthly_target_val > 0 else self.thresholds.get("progress", 0.8)

            gap = 0
            if group_progress_target > 0 and monthly_completion_rate < group_progress_target and monthly_target > 0:
                gap = int((group_progress_target - monthly_completion_rate) * monthly_target)

            # LP 明细：今日例子=0 且月进度低于小组目标
            lagging_lps = []
            for row in lp_rows:
                lp_name = row[tuple(cols["lp"])]
                lp_today = self._safe_float(row[tuple(cols["today_count"])])
                lp_total = self._safe_float(row[tuple(cols["total_count"])])
                lp_monthly_target = self._safe_float(row[tuple(cols["monthly_target"])])
                lp_monthly_rate = lp_total / lp_monthly_target if lp_monthly_target > 0 else 0
                if lp_today == 0 and lp_monthly_rate < group_progress_target:
                    lagging_lps.append({
                        "lp": lp_name,
                        "monthly_rate": lp_monthly_rate,
                    })
            # 按月进度升序排列
            lagging_lps.sort(key=lambda x: x["monthly_rate"], reverse=True)

            # 小组预警：今日达标率低于 100%，而不是只看今日例子是否为 0
            has_alert = today_target > 0 and today_count < today_target

            results.append({
                "group": group,
                "tl": tl_name,
                "today_target": today_target,
                "today_count": today_count,
                "today_completion_rate": today_completion_rate,
                "monthly_target": monthly_target,
                "total_count": total_count,
                "monthly_completion_rate": monthly_completion_rate,
                "group_progress_target": group_progress_target,
                "gap": gap,
                "has_alert": has_alert,
                "lagging_lps": lagging_lps,
            })

        return results

    def _safe_float(self, val):
        try:
            return float(val) if pd.notna(val) else 0
        except (ValueError, TypeError):
            return 0
