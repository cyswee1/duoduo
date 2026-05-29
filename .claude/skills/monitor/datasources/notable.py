"""钉钉多维表格（Notable）数据源 — 读取港澳团队每日目标登记。"""
import time
import datetime
import requests


SHEET_SCENARIO_MAP = {
    "转介绍日监控": "intro",
    "续费日监控": "renewal",
    "服务监控": "service",
}

# 每个场景至少要有一个非空非零的字段才算"活跃"
SCENARIO_REQUIRED_FIELDS = {
    "intro":   ["今日例子目标", "转介绍例子进度目标", "外呼跟进目标"],
    "renewal": ["续费目标", "通时目标", "通次目标", "外呼跟进目标"],
    "service": ["首通及时跟进目标", "首课及时跟进目标", "首专及时跟进目标"],
}


class NotableDataSource:
    """从钉钉多维表格读取港澳团队每日目标，支持多 sheet 场景路由"""

    def __init__(self, config, secrets_loader):
        self.config = config
        self.secrets = secrets_loader()
        self.app_key = self.secrets[config["app_key"]]
        self.app_secret = self.secrets[config["app_secret_key"]]
        self.base_id = config["base_id"]
        self.operator_userid = self.secrets.get(config.get("operator_userid_key", ""), "")
        self.table_url = config.get("table_url", "")
        self._token_cache = {"token": None, "expire_at": 0}
        self._union_id_cache = None
        self._sheets_cache = None

    def get_active_scenarios(self, team=None):
        """检测哪些 sheet 有今日填写的目标数据，返回场景名列表（如 ['intro', 'renewal']）

        Args:
            team: '港澳' / '美澳'，只检查该团队的记录；None 则检查所有记录
        """
        token = self._get_access_token()
        union_id = self._get_union_id(token)
        sheets = self._list_sheets(token, union_id)
        today = datetime.date.today()

        active = []
        for sheet in sheets:
            name = sheet.get("name", "")
            sheet_id = sheet.get("id", "")
            scenario = SHEET_SCENARIO_MAP.get(name)
            if not scenario:
                continue
            records = self._get_records(token, union_id, sheet_id, max_results=20)
            required = SCENARIO_REQUIRED_FIELDS.get(scenario, [])
            has_data = any(
                self._is_today(rec.get("lastModifiedTime")) and
                self._matches_team(rec.get("fields", {}).get("小组", ""), team) and
                any(
                    rec.get("fields", {}).get(f) not in (None, "", 0, "0")
                    for f in required
                )
                for rec in records
            )
            if has_data:
                active.append(scenario)
        return active

    def _matches_team(self, group, team):
        """判断小组名是否属于指定团队"""
        if not team:
            return True
        if team == "港澳":
            return group.startswith("港澳") or group.startswith("台湾")
        if team == "美澳":
            return group.startswith("美澳")
        return True

    def _is_today(self, ts_ms):
        """判断毫秒时间戳是否是今天"""
        if not ts_ms:
            return False
        try:
            dt = datetime.datetime.fromtimestamp(int(ts_ms) / 1000)
            return dt.date() == datetime.date.today()
        except (ValueError, TypeError, OSError):
            return False

    def read_targets(self, scenario, team=None, today_only=False):
        """读取指定场景 sheet 的目标数据

        Args:
            scenario: 'intro' / 'renewal' / 'service'
            team: 可选，按小组前缀过滤（'美澳'/'港澳'）
            today_only: 为 True 时只返回今日修改过的记录（用于美澳覆盖逻辑）

        Returns:
            dict: {小组名: {字段: 值}}
        """
        sheet_name = {v: k for k, v in SHEET_SCENARIO_MAP.items()}.get(scenario)
        if not sheet_name:
            raise ValueError(f"未知场景: {scenario}")

        token = self._get_access_token()
        union_id = self._get_union_id(token)
        sheets = self._list_sheets(token, union_id)

        sheet_id = next((s["id"] for s in sheets if s.get("name") == sheet_name), None)
        if not sheet_id:
            return {}

        records = self._get_records(token, union_id, sheet_id, max_results=100)
        result = {}
        for rec in records:
            if today_only and not self._is_today(rec.get("lastModifiedTime")):
                continue
            fields = rec.get("fields", {})
            group = fields.get("小组")
            if not group:
                continue
            if team == "美澳" and not group.startswith("美澳"):
                continue
            if team == "港澳" and not (group.startswith("港澳") or group.startswith("台湾")):
                continue
            result[group] = self._parse_fields(scenario, fields)
        return result

    def _parse_fields(self, scenario, fields):
        """按场景解析字段，统一转为 DingTalkReportDataSource 兼容的 key"""
        target = {}
        if scenario == "intro":
            target["转介绍例子进度目标"] = self._float(fields.get("转介绍例子进度目标"))
            target["外呼跟进目标"] = self._float(fields.get("外呼跟进目标"))
            if "今日例子目标" in fields:
                target["今日例子目标"] = self._float(fields.get("今日例子目标"))
            # 跟进池子是多选字段，值为 [{name: ...}, ...] 或字符串列表
            pool_name_mapping = self.config.get("pool_name_mapping", {})
            pools_raw = fields.get("跟进池子", [])
            if pools_raw:
                if isinstance(pools_raw, list):
                    raw_names = [p["name"] if isinstance(p, dict) else str(p) for p in pools_raw]
                else:
                    raw_names = [str(pools_raw)]
                target["跟进池子"] = [pool_name_mapping.get(n, n) for n in raw_names]
        elif scenario == "renewal":
            target["外呼跟进目标"] = self._float(fields.get("外呼跟进目标"))
            for k in ["续费目标", "通时目标", "通次目标"]:
                if k in fields:
                    target[k] = self._float(fields.get(k))
        elif scenario == "service":
            key_map = {
                "首通及时跟进目标": "月度首通及时跟进目标",
                "首课及时跟进目标": "月度首课及时跟进目标",
                "首专及时跟进目标": "月度首专及时跟进目标",
                "服务池外呼跟进目标": "服务池外呼跟进率目标",
                "服务池有效跟进目标": "服务池综合有效跟进率目标",
            }
            for sheet_key, target_key in key_map.items():
                if sheet_key in fields:
                    target[target_key] = self._float(fields.get(sheet_key))
        return target

    def _list_sheets(self, token, union_id):
        if self._sheets_cache is not None:
            return self._sheets_cache
        resp = requests.get(
            f"https://api.dingtalk.com/v1.0/notable/bases/{self.base_id}/sheets",
            headers={"x-acs-dingtalk-access-token": token},
            params={"operatorId": union_id},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"列举 sheets 失败: {resp.status_code} {resp.text}")
        self._sheets_cache = resp.json().get("value", [])
        return self._sheets_cache

    def _get_records(self, token, union_id, sheet_id, max_results=100):
        resp = requests.get(
            f"https://api.dingtalk.com/v1.0/notable/bases/{self.base_id}/sheets/{sheet_id}/records",
            headers={"x-acs-dingtalk-access-token": token},
            params={"operatorId": union_id, "maxResults": max_results},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("records", [])

    def _get_union_id(self, token):
        if self._union_id_cache:
            return self._union_id_cache
        r = requests.post(
            "https://oapi.dingtalk.com/topapi/v2/user/get",
            params={"access_token": token},
            json={"userid": self.operator_userid},
            timeout=10,
        )
        data = r.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"查询 unionId 失败: {data}")
        self._union_id_cache = data["result"]["unionid"]
        return self._union_id_cache

    def _get_access_token(self):
        now = time.time()
        if self._token_cache["token"] and self._token_cache["expire_at"] > now + 60:
            return self._token_cache["token"]
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/oauth2/accessToken",
            json={"appKey": self.app_key, "appSecret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if "accessToken" not in data:
            raise RuntimeError(f"获取 accessToken 失败: {data}")
        self._token_cache["token"] = data["accessToken"]
        self._token_cache["expire_at"] = now + int(data.get("expireIn", 7200))
        return self._token_cache["token"]

    def _float(self, val):
        if val is None:
            return 0
        try:
            s = str(val).strip()
            if s.endswith("%"):
                return float(s[:-1]) / 100
            return float(s)
        except (ValueError, TypeError):
            return 0
