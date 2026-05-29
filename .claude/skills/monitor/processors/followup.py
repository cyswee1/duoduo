"""外呼跟进数据处理器 — 参数化版本。"""
import pandas as pd


class FollowupProcessor:
    """参数化的外呼跟进预警处理器"""

    def __init__(self, phase_config):
        self.config = phase_config
        self.pool_configs = phase_config["pool_configs"]
        self.thresholds = phase_config["thresholds"]

    def extract_warnings(self, excel_path, team_config, notable_targets):
        """提取外呼跟进预警（含 LP 明细）

        Returns:
            dict: {小组名: [{pool, rate, target, status, gap, lagging_lps}, ...]}
        """
        df = pd.read_excel(excel_path, header=None, engine="openpyxl")

        # 找数据起始行：col1 有值且 col2='总计' 的第一行
        summary_start = None
        lp_start = None
        for i in range(len(df)):
            c1, c2 = df.iloc[i, 1], df.iloc[i, 2] if df.shape[1] > 2 else None
            if str(c2) == '总计' and summary_start is None:
                summary_start = i
            # LP 段：col2 是人名（非总计/nan），且 col1 是小组名或 nan
            if summary_start is not None and lp_start is None and i > summary_start + 5:
                if str(c1) != 'nan' and str(c2) not in ['nan', '总计', '']:
                    lp_start = i
                    break

        # 构建 LP 段的小组→LP列表映射
        lp_data = {}  # {小组: [{lp, col_offset_rate}, ...]}
        if lp_start is not None:
            current_group = None
            for i in range(lp_start, len(df)):
                row = df.iloc[i]
                c1, c2 = row.iloc[1], row.iloc[2] if df.shape[1] > 2 else None
                if str(c1) != 'nan' and str(c1) != '':
                    current_group = c1
                if current_group and str(c2) not in ['nan', '总计', '']:
                    if current_group not in lp_data:
                        lp_data[current_group] = []
                    lp_data[current_group].append(row)

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

                # pool_configs 的 column_offset 指向池子学员数列，外呼跟进率在下一列
                rate_col = col_offset + 1
                rate = self._get_group_rate(df, summary_start, group, rate_col)

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
                    # 提取落后 LP（跟进率 < target）
                    lagging_lps = self._get_lagging_lps(
                        lp_data.get(group, []), rate_col, target
                    )
                    group_warnings.append({
                        "pool": pool_name,
                        "rate": rate,
                        "target": target,
                        "status": status,
                        "gap": gap,
                        "lagging_lps": lagging_lps,
                    })

            if group_warnings:
                warnings_per_group[group] = group_warnings

        return warnings_per_group

    def _get_group_rate(self, df, summary_start, group, col_offset):
        """从汇总段找小组跟进率"""
        if summary_start is None:
            return None
        for i in range(summary_start, summary_start + 30):
            if i >= len(df):
                break
            row = df.iloc[i]
            if str(row.iloc[1]) == group:
                val = row.iloc[col_offset] if df.shape[1] > col_offset else None
                if val is not None and pd.notna(val):
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
        return None

    def _get_lagging_lps(self, lp_rows, col_offset, target):
        """从 LP 行列表中提取跟进率低于目标的 LP"""
        lagging = []
        for row in lp_rows:
            lp_name = row.iloc[2] if len(row) > 2 else None
            if pd.isna(lp_name) or str(lp_name) in ['nan', '总计', '']:
                continue
            val = row.iloc[col_offset] if len(row) > col_offset else None
            if val is None or pd.isna(val):
                continue
            try:
                rate = float(val)
            except (ValueError, TypeError):
                continue
            if rate < target:
                lagging.append({"lp": lp_name, "rate": rate})
        lagging.sort(key=lambda x: x["rate"], reverse=True)
        return lagging
