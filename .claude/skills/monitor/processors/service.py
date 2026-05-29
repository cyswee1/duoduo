"""服务指标处理器 — 多指标对比告警。

告警规则：
- 首通/首课/首专及时跟进率 < 80% → 告警
- 服务池外呼跟进率 < 60% → 告警
- 服务池综合有效跟进率 < 目标 → 告警
"""
import pandas as pd


class ServiceProcessor:
    """服务指标多报表对比处理器"""

    def __init__(self, phase_config):
        self.config = phase_config
        self.excel_cfg = phase_config["excel_parsing"]
        self.thresholds = phase_config["thresholds"]

    def evaluate_alerts(self, excel_paths, team_config, targets):
        """评估服务指标告警

        Args:
            excel_paths: dict of {report_key: Path}
            team_config: 团队配置
            targets: 钉钉日志读取的目标 {小组: {字段: 值}}

        Returns:
            list[dict]: 每个小组的指标数据和告警状态
        """
        dfs = {}
        for report_key, path in excel_paths.items():
            if report_key not in self.excel_cfg:
                continue
            cfg = self.excel_cfg[report_key]
            header_rows = cfg.get("header_rows")
            if not header_rows:
                # header=None 模式：整张表原始读取，数据行由 data_start_row 指定
                dfs[report_key] = pd.read_excel(path, header=None, engine="openpyxl")
            else:
                header = header_rows[0] if len(header_rows) == 1 else header_rows
                dfs[report_key] = pd.read_excel(path, header=header, engine="openpyxl")

        results = []
        for group in team_config["groups"]:
            tl_info = team_config["tl_map"].get(group)
            if not tl_info:
                continue
            tl_name = tl_info["name"]

            target_data = targets.get(group, {})
            if not target_data:
                continue
            first_call_target = target_data.get("月度首通及时跟进目标", self.thresholds.get("first_call_rate", 0.8))
            first_lesson_target = target_data.get("月度首课及时跟进目标", self.thresholds.get("first_lesson_rate", 0.8))
            first_specialist_target = target_data.get("月度首专及时跟进目标", self.thresholds.get("first_specialist_rate", 0.8))
            pool_followup_target = target_data.get("服务池外呼跟进率目标", self.thresholds.get("service_pool_followup_rate", 0.6))
            pool_effective_target = target_data.get("服务池综合有效跟进率目标", self.thresholds.get("service_pool_effective_rate", 0.6))

            metrics = {
                "group": group,
                "tl": tl_name,
                "first_call_target": first_call_target,
                "first_call_rate": 0,
                "first_lesson_target": first_lesson_target,
                "first_lesson_rate": 0,
                "first_specialist_target": first_specialist_target,
                "first_specialist_rate": 0,
                "pool_followup_target": pool_followup_target,
                "pool_followup_rate": 0,
                "pool_effective_target": pool_effective_target,
                "pool_effective_rate": 0,
                "alerts": [],
            }

            # 首通：header=None，用列索引，data_start_row 跳过表头行
            if "first_call" in dfs:
                df = dfs["first_call"]
                cfg = self.excel_cfg["first_call"]
                start = cfg.get("data_start_row", 3)
                grp_col = cfg.get("group_col_index", 1)
                rate_col = cfg.get("first_call_rate_col_index", 20)
                data = df.iloc[start:].reset_index(drop=True)
                rows = data[data.iloc[:, grp_col] == group]
                if not rows.empty:
                    rate = self._safe_float(rows.iloc[0].iloc[rate_col])
                    metrics["first_call_rate"] = rate
                    if rate < first_call_target:
                        metrics["alerts"].append("首通低于目标")

            # 首课：海外思维学管服务指标统计表（-48h），小组列=团队，列名=首课及时跟进率
            if "first_lesson_stats" in dfs:
                rate = self._extract_by_colname(
                    dfs["first_lesson_stats"],
                    self.excel_cfg["first_lesson_stats"]["columns"],
                    group, "first_lesson_rate",
                )
                metrics["first_lesson_rate"] = rate
                if rate < first_lesson_target:
                    metrics["alerts"].append("首课低于目标")

            # 首专：海外思维学管服务指标统计表（-72h），小组列=团队，列名=首专及时跟进率
            if "first_specialist_stats" in dfs:
                rate = self._extract_by_colname(
                    dfs["first_specialist_stats"],
                    self.excel_cfg["first_specialist_stats"]["columns"],
                    group, "first_specialist_rate",
                )
                metrics["first_specialist_rate"] = rate
                if rate < first_specialist_target:
                    metrics["alerts"].append("首专低于目标")

            # 服务池：思维转介绍过程跟进报表（多层表头）
            if "followup" in dfs:
                cols = self.excel_cfg["followup"]["columns"]
                pool_rate = self._extract_rate_multiindex(dfs["followup"], cols, group, "service_pool_followup_rate")
                effective_rate = self._extract_rate_multiindex(dfs["followup"], cols, group, "service_pool_effective_rate")
                metrics["pool_followup_rate"] = pool_rate
                metrics["pool_effective_rate"] = effective_rate
                if pool_rate < pool_followup_target:
                    metrics["alerts"].append("服务池跟进低于目标")
                if effective_rate < pool_effective_target:
                    metrics["alerts"].append("有效跟进低于目标")

            metrics["has_alert"] = len(metrics["alerts"]) > 0
            results.append(metrics)

        return results

    def _extract_by_colname(self, df, cols, group, rate_key):
        """单层表头：按列名提取指定小组的指标值"""
        group_col = cols["team_group"][0]
        rows = df[df[group_col] == group]
        if rows.empty or rate_key not in cols:
            return 0
        col_name = cols[rate_key][0]
        return self._safe_float(rows.iloc[0].get(col_name, 0))

    def _extract_rate_multiindex(self, df, cols, group, rate_key):
        """多层表头：按 tuple 列名提取指定小组的指标值"""
        group_col = tuple(cols["team_group"])
        rows = df[df[group_col] == group]
        if rows.empty or rate_key not in cols:
            return 0
        return self._safe_float(rows.iloc[0].get(tuple(cols[rate_key]), 0))

    def _safe_float(self, val):
        try:
            return float(val) if pd.notna(val) else 0
        except (ValueError, TypeError):
            return 0
