"""钉钉日志（OA Report）数据源 — 读取 TL 每日目标日志。"""
import json
import time
import requests


class DingTalkReportDataSource:
    """从钉钉日志读取 TL 填写的每日跟进目标"""

    def __init__(self, config, secrets_loader):
        self.config = config
        self.secrets = secrets_loader()
        self.app_key = self.secrets[config["app_key"]]
        self.app_secret = self.secrets[config["app_secret_key"]]
        self.template_name = config["template_name"]
        self.fields = config["fields"]
        self.team_user_map = config.get("team_user_map", {})

    def read_schedule_and_targets(self, team, date_str=None):
        """读取美澳团队的明日节奏规划和对应目标

        Returns:
            dict: {
                'scenarios': ['intro', 'renewal'],  # 今日要跑的场景
                'targets': {小组: {字段: 值}}        # 各场景目标合并
            }
        """
        targets_raw = self.read_targets(team, date_str)
        scenarios = set()

        scenario_field_map = {
            "转介绍": "intro",
            "续费": "renewal",
            "服务": "service",
        }

        for group, data in targets_raw.items():
            schedule_raw = data.get("明日节奏规划", [])
            if isinstance(schedule_raw, str):
                try:
                    schedule_raw = json.loads(schedule_raw)
                except (ValueError, TypeError):
                    schedule_raw = [schedule_raw]
            if isinstance(schedule_raw, list):
                for item in schedule_raw:
                    scenario = scenario_field_map.get(str(item).strip())
                    if scenario:
                        scenarios.add(scenario)

        return {
            "scenarios": sorted(scenarios),
            "targets": targets_raw,
        }

    def read_targets(self, team, date_str=None):
        """读取指定团队 TL 的日志目标

        Args:
            team: 团队名（如 '美澳' / '港澳'）
            date_str: 日期字符串 YYYY-MM-DD，默认取昨天的日志

        Returns:
            dict: {小组名: {字段: 值}}
        """
        token = self._get_access_token()
        userids = self._get_team_userids(team)

        if date_str is None:
            yesterday = time.time() - 86400
            start_time = int(yesterday // 86400 * 86400 * 1000)
        else:
            import datetime
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            start_time = int(dt.timestamp() * 1000)

        end_time = start_time + 86400 * 1000

        result = {}
        for group_name, userid in userids.items():
            report = self._fetch_latest_report(
                token, userid, start_time, end_time
            )
            if not report:
                continue
            target = self._parse_report_fields(report)
            if target:
                result[group_name] = target

        return result

    def get_registered_tls(self, team, tl_names, date_str=None):
        """获取已提交日志的 TL 列表

        Args:
            team: 团队名
            tl_names: TL 名称列表
            date_str: 日期，默认昨天

        Returns:
            (已提交, 未提交) 元组
        """
        targets = self.read_targets(team, date_str)
        registered_groups = set(targets.keys())
        registered = []
        unregistered = []
        for tl_name in tl_names:
            found = any(tl_name in group for group in registered_groups)
            if found:
                registered.append(tl_name)
            else:
                unregistered.append(tl_name)
        return registered, unregistered

    def _get_team_userids(self, team):
        """获取团队内 TL 的 userid 映射

        Returns:
            dict: {小组名: userid}
        """
        team_map = self.team_user_map.get(team, {})
        if not team_map:
            raise ValueError(
                f"团队 '{team}' 未在 team_user_map 中配置"
            )
        return team_map

    def _fetch_latest_report(self, token, userid, start_time, end_time):
        """拉取用户在时间范围内最近一次提交的日志（按 create_time 降序取首条）"""
        url = "https://oapi.dingtalk.com/topapi/report/list"
        resp = requests.post(
            url,
            params={"access_token": token},
            json={
                "userid": userid,
                "start_time": start_time,
                "end_time": end_time,
                "template_name": self.template_name,
                "cursor": 0,
                "size": 20,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("errcode") != 0:
            return None
        records = data.get("result", {}).get("data_list", [])
        if not records:
            return None
        return max(records, key=lambda r: r.get("create_time", 0))

    def _parse_report_fields(self, report):
        """从日志内容中提取结构化目标字段

        日志结构示例（"海外益智团队日志"）：
          contents:
            - {key: '续费明日目标', value: '[["续费目标","通时目标",...],["5000","100",...]]'}
            - {key: '转介绍明日目标', value: '[["例子目标",...],["20",...]]'}

        每个 section（含"目标"两字的 key）value 是 [[字段名...],[值...]] 的 JSON。
        本方法按 section 解析，返回扁平化目标字典。同名字段以 self.section_priority
        指定的 section 优先（默认按 self.fields 中提到的 section 推断）。

        Returns:
            dict: 扁平化字段字典，含 self.fields 配置的所有字段 + "跟进池子"
        """
        contents = report.get("contents", [])
        flat_map = {}
        sections = {}  # {section_key: {field: value}}
        for item in contents:
            key = item.get("key", "")
            raw = item.get("value", "")
            parsed = self._try_parse_section(raw)
            if parsed is not None:
                sections[key] = parsed
                # 优先保留可解析的 section 值
                flat_map[key] = raw
            else:
                # 只在 key 不存在时写入（避免文字说明覆盖选项列表）
                flat_map.setdefault(key, raw)

        priority_sections = self.config.get("section_priority", [])
        merged = {}
        # 先填非优先 section，再填优先 section（覆盖）
        for sec_name, fields in sections.items():
            if sec_name in priority_sections:
                continue
            for k, v in fields.items():
                merged.setdefault(k, v)
        for sec_name in priority_sections:
            if sec_name not in sections:
                continue
            for k, v in sections[sec_name].items():
                merged[k] = v

        # 平铺字段（未识别为 section 的）
        for k, v in flat_map.items():
            if k in sections:
                continue
            merged.setdefault(k, v)

        target = {}
        for _, dingtalk_field in self.fields.items():
            if dingtalk_field in merged:
                target[dingtalk_field] = self._coerce_value(merged[dingtalk_field])

        if "跟进池子" in merged:
            target["跟进池子"] = self._normalize_pools(merged["跟进池子"])

        # 明日节奏规划：section 里的第一行是选项列表（如 ["转介绍","续费"]）
        if "明日节奏规划" in sections:
            # sections["明日节奏规划"] 是 {字段名: 值} 形式，但节奏规划是单行选项
            # 直接从 flat_map 取原始值解析
            pass
        if "明日节奏规划" in flat_map:
            raw_schedule = flat_map["明日节奏规划"]
            parsed = self._try_parse_section(raw_schedule)
            if parsed is not None:
                # [[选项1, 选项2, ...], [True/False, ...]] 格式
                # 取第一行作为选项名列表
                target["明日节奏规划"] = list(parsed.keys())
            elif isinstance(raw_schedule, str):
                try:
                    val = json.loads(raw_schedule)
                    if isinstance(val, list):
                        target["明日节奏规划"] = val
                except (ValueError, TypeError):
                    target["明日节奏规划"] = [raw_schedule]

        return target

    def _try_parse_section(self, raw):
        """尝试把 value 解析为 [[字段名...],[值...]] 二维结构。
        返回 dict 或 None。"""
        if not isinstance(raw, str) or not raw.startswith("["):
            return None
        import json
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not (isinstance(data, list) and len(data) >= 2
                and isinstance(data[0], list) and isinstance(data[1], list)):
            return None
        keys, values = data[0], data[1]
        if len(keys) != len(values):
            return None
        return {k: v for k, v in zip(keys, values) if v is not None}

    def _coerce_value(self, value):
        """把日志原始值转为数字（支持 '60%'/'5000'）或保留字符串。"""
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return 0
            if s.endswith("%"):
                try:
                    return float(s[:-1]) / 100
                except ValueError:
                    return s
            try:
                return float(s)
            except ValueError:
                return s
        return value

    def _normalize_pools(self, raw):
        """池子字段可能是 list 或逗号分隔字符串，统一转为 list。"""
        pool_mapping = self.config.get("pool_name_mapping", {})
        if isinstance(raw, list):
            names = [str(n).strip() for n in raw if n]
        elif isinstance(raw, str):
            names = [p.strip() for p in raw.split(",") if p.strip()]
        else:
            return raw
        return [pool_mapping.get(n, n) for n in names]

    def _get_access_token(self):
        url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        resp = requests.post(
            url,
            json={"appKey": self.app_key, "appSecret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if "accessToken" not in data:
            raise RuntimeError(f"获取 accessToken 失败: {data}")
        return data["accessToken"]
