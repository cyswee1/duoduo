"""续费业绩处理器 — 复合条件告警。

外呼跟进率取数规则：
- 池子含"一续" -> pool_followup（思维目标池未续跟进情况）总计列
- 池子含"统合"或为空 -> pool_followup_rate（思维目标池未续跟进_统合）总计列
"""
import pandas as pd


class RenewalProcessor:

    _DC_GROUP_COL = 1
    _DC_TL_COL = 2
    _DC_COUNT_COL = 5
    _DC_DURATION_COL = 7
    _DC_GMV_COL = 14

    _POOL_GROUP_COL = 1
    _POOL_TL_COL = 2
    _POOL_RATE_COL = 4

    def __init__(self, phase_config):
        self.config = phase_config
        self.excel_cfg = phase_config["excel_parsing"]

    def evaluate_alerts(self, excel_paths, team_config, targets):
        if "daily_call" not in excel_paths:
            print("  ✗ daily_call 报表缺失，无法评估续费告警")
            return []
        daily_raw = pd.read_excel(
            excel_paths["daily_call"], header=None, engine="openpyxl"
        )
        pool_followup_df = pd.read_excel(
            excel_paths["pool_followup"], header=None, engine="openpyxl"
        ) if "pool_followup" in excel_paths else None

        pool_followup_rate_df = pd.read_excel(
            excel_paths["pool_followup_rate"], header=None, engine="openpyxl"
        ) if "pool_followup_rate" in excel_paths else None

        results = []
        for group in team_config["groups"]:
            tl_info = team_config["tl_map"].get(group)
            if not tl_info:
                continue
            tl_name = tl_info["name"]

            target_data = targets.get(group, {})
            if not target_data:
                continue
            renewal_target = target_data.get("续费目标", 0)
            duration_target = target_data.get("通时目标", 0)
            count_target = target_data.get("通次目标", 0)
            followup_target = target_data.get("外呼跟进目标", 0)
            pool_names = target_data.get("跟进池子", [])
            if isinstance(pool_names, str):
                pool_names = [pool_names] if pool_names else []

            mask = (daily_raw.iloc[:, self._DC_GROUP_COL] == group) & \
                   (daily_raw.iloc[:, self._DC_TL_COL] == tl_name)
            group_rows = daily_raw[mask]
            if group_rows.empty:
                gmv, duration, call_count = 0.0, 0.0, 0.0
            else:
                row = group_rows.iloc[0]
                gmv = self._safe_float(row.iloc[self._DC_GMV_COL])
                duration = self._safe_float(row.iloc[self._DC_DURATION_COL])
                call_count = self._safe_float(row.iloc[self._DC_COUNT_COL])

            followup_rate = self._get_followup_rate(
                pool_names, group, tl_name, pool_followup_df, pool_followup_rate_df
            )

            lp_mask = (
                (daily_raw.iloc[:, self._DC_GROUP_COL] == group) &
                (daily_raw.iloc[:, self._DC_TL_COL] != tl_name) &
                (daily_raw.iloc[:, self._DC_TL_COL].notna()) &
                (daily_raw.iloc[:, self._DC_TL_COL].astype(str).str.strip() != "") &
                (daily_raw.iloc[:, self._DC_TL_COL].astype(str) != "nan")
            )
            lagging_lps = []
            for _, lp_row in daily_raw[lp_mask].iterrows():
                lp_name = str(lp_row.iloc[self._DC_TL_COL]).strip()
                lp_gmv = self._safe_float(lp_row.iloc[self._DC_GMV_COL])
                lp_duration = self._safe_float(lp_row.iloc[self._DC_DURATION_COL])
                lp_count = self._safe_float(lp_row.iloc[self._DC_COUNT_COL])
                lp_followup_rate = self._get_followup_rate(
                    pool_names, group, lp_name, pool_followup_df, pool_followup_rate_df
                )
                cond_a = (lp_gmv == 0 and duration_target > 0 and count_target > 0
                          and lp_duration < duration_target * 0.6
                          and lp_count < count_target * 0.6)
                cond_b = (lp_gmv == 0 and followup_target > 0
                          and lp_followup_rate < followup_target * 0.6)
                if cond_a or cond_b:
                    lagging_lps.append(lp_name)

            alerts = []
            if renewal_target > 0 and gmv < renewal_target:
                alerts.append("续费未达标")
            if gmv == 0 and duration_target > 0 and count_target > 0:
                if duration < duration_target * 0.6 and call_count < count_target * 0.6:
                    alerts.append("低活跃")
            if gmv == 0 and followup_target > 0:
                if followup_rate < followup_target * 0.6:
                    alerts.append("低跟进")

            renewal_gap = renewal_target - gmv if renewal_target > 0 else 0
            followup_gap = followup_target - followup_rate if followup_target > 0 else 0

            results.append({
                "group": group,
                "tl": tl_name,
                "pool_name": "、".join(pool_names) if pool_names else "",
                "renewal_target": renewal_target,
                "renewal_gmv": gmv,
                "renewal_gap": max(0, renewal_gap),
                "duration_target": duration_target,
                "duration": duration,
                "count_target": count_target,
                "call_count": call_count,
                "followup_target": followup_target,
                "followup_rate": followup_rate,
                "followup_gap": max(0, followup_gap),
                "alerts": alerts,
                "has_alert": len(alerts) > 0,
                "lagging_lps": lagging_lps,
            })

        return results

    def _get_followup_rate(self, pool_names, group, tl_name,
                           pool_followup_df, pool_followup_rate_df):
        """按池子路由到对应报表，取该行总计外呼跟进率（col4）。
        池子含"一续" -> pool_followup；否则/为空 -> pool_followup_rate。
        """
        has_yixu = any("一续" in p for p in pool_names)
        df = pool_followup_df if has_yixu else pool_followup_rate_df
        if df is None:
            return 0
        mask = (df.iloc[:, self._POOL_GROUP_COL] == group) & \
               (df.iloc[:, self._POOL_TL_COL] == tl_name)
        rows = df[mask]
        if rows.empty:
            return 0
        return self._safe_float(rows.iloc[0].iloc[self._POOL_RATE_COL])

    def _safe_float(self, val):
        try:
            return float(val) if pd.notna(val) else 0
        except (ValueError, TypeError):
            return 0
