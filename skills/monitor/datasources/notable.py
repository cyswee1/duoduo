"""钉钉多维表格（Notable）数据源 — 参数化版本。"""
import requests


class NotableDataSource:
    """参数化的钉钉 Notable 读取器"""

    def __init__(self, config, secrets_loader):
        """
        Args:
            config: datasources.notable 配置块
            secrets_loader: 凭证加载函数
        """
        self.config = config
        self.secrets = secrets_loader()
        self.base_id = self.secrets[config["base_id_key"]]
        self.sheet_id = self.secrets[config["sheet_id_key"]]
        self.app_key = self.secrets[config["app_key"]]
        self.app_secret = self.secrets[config["app_secret_key"]]
        self.my_userid = self.secrets[config["my_userid_key"]]
        self.fields = config["fields"]
        self.pool_mapping = config.get("pool_name_mapping", {})

    def get_table_url(self):
        """生成多维表格 URL"""
        template = self.config.get("table_url_template", "")
        return template.format(base_id=self.base_id, sheet_id=self.sheet_id)

    def read_targets(self, team):
        """读取指定团队的目标登记

        Args:
            team: 团队名（如 '美澳' / '港澳'）

        Returns:
            dict: {小组名: {字段: 值}}
        """
        token = self._get_access_token()
        union_id = self._get_union_id(token)

        headers = {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }

        url = f"https://api.dingtalk.com/v1.0/notable/bases/{self.base_id}/sheets/{self.sheet_id}/records"
        resp = requests.get(
            url,
            headers=headers,
            params={"operatorId": union_id, "maxResults": 100},
            timeout=15,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"读取 Notable 失败 {resp.status_code}: {resp.text}")

        data = resp.json()
        records = data.get("records", [])

        # 转换成统一格式
        result = {}
        for rec in records:
            fields = rec.get("fields", {})
            group_name = fields.get(self.fields["group_name"])
            if not group_name:
                continue

            # 根据 team 筛选
            if team == "美澳" and not group_name.startswith("美澳"):
                continue
            if team == "港澳" and not (group_name.startswith("港澳") or group_name.startswith("台湾")):
                continue

            target = {}

            # 转介绍例子进度目标
            progress_str = fields.get(self.fields["progress_target"], "")
            if progress_str:
                try:
                    target["小组进度目标"] = float(progress_str)
                except ValueError:
                    pass

            # 今日例子目标
            daily_str = fields.get(self.fields["daily_target"], "")
            if daily_str:
                try:
                    target["小组例子目标"] = int(daily_str)
                except ValueError:
                    pass

            # 跟进池子（多选字段）
            pools_raw = fields.get(self.fields["pools"], [])
            if pools_raw:
                pool_names = [p["name"] for p in pools_raw if isinstance(p, dict) and "name" in p]
                mapped = [self.pool_mapping.get(name, name) for name in pool_names]
                target["跟进池子"] = mapped

            # 外呼跟进目标
            followup_str = fields.get(self.fields["followup_target"], "")
            if followup_str:
                try:
                    target["外呼跟进目标"] = float(followup_str)
                except ValueError:
                    pass

            result[group_name] = target

        return result

    def get_registered_tls(self, team, tl_names):
        """获取已登记的 TL 列表

        Args:
            team: 团队名
            tl_names: TL 名称列表

        Returns:
            (已登记, 未登记) 元组
        """
        targets = self.read_targets(team)
        registered_groups = set(targets.keys())
        registered = []
        unregistered = []

        for tl_name in tl_names:
            # 查找该 TL 对应的小组是否已登记
            found = any(tl_name in group for group in registered_groups)
            if found:
                registered.append(tl_name)
            else:
                unregistered.append(tl_name)

        return registered, unregistered

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

    def _get_union_id(self, token):
        url = "https://oapi.dingtalk.com/topapi/v2/user/get"
        r = requests.post(
            url,
            params={"access_token": token},
            json={"userid": self.my_userid},
            timeout=10,
        )
        data = r.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"查询 unionId 失败: {data}")
        return data["result"]["unionid"]
