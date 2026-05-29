"""钉钉通知器 — 参数化版本。"""
import requests
import time


class DingTalkNotifier:
    """参数化的钉钉通知器"""

    def __init__(self, config, secrets_loader):
        """
        Args:
            config: notifier 配置块
            secrets_loader: 凭证加载函数
        """
        self.config = config
        self.secrets = secrets_loader()
        self.robot_code = self.secrets[config["robot_code_key"]]
        self.app_key = self.secrets[config["app_key"]]
        self.app_secret = self.secrets[config["app_secret_key"]]
        self._token_cache = {"token": None, "expire_at": 0}

    def send_image_with_text(self, chat_id, image_bytes, title, text, at_userids=None):
        """上传图片并嵌入 markdown，图片+文字一条消息发出"""
        import json
        media_id = self._upload_image(image_bytes)
        token = self._get_access_token()

        markdown = f"![预警表格]({media_id})\n\n{text}"
        msg_param = {"title": title, "text": markdown}
        if at_userids:
            msg_param["atUserIds"] = at_userids

        payload = {
            "robotCode": self.robot_code,
            "openConversationId": chat_id,
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/robot/groupMessages/send",
            headers={"x-acs-dingtalk-access-token": token, "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        data = resp.json() if resp.text else {}
        if resp.status_code != 200 or data.get("code"):
            raise RuntimeError(f"发送失败 status={resp.status_code} resp={data}")
        return data

    def send_webhook_markdown(self, webhook_url, title, markdown_text, at_mobiles=None):
        """通过自定义 webhook 发送 markdown 消息，支持 atMobiles @mention"""
        mention_text = ""
        if at_mobiles:
            mention_text = "\n\n" + " ".join(f"@{m}" for m in at_mobiles)
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": markdown_text + mention_text,
            },
            "at": {
                "atMobiles": [str(m) for m in at_mobiles] if at_mobiles else [],
                "isAtAll": False,
            },
        }
        resp = requests.post(webhook_url, json=payload, timeout=15)
        data = resp.json() if resp.text else {}
        if resp.status_code != 200 or data.get("errcode", 0) != 0:
            raise RuntimeError(f"webhook 发送失败 status={resp.status_code} resp={data}")
        return data

    def send_markdown(self, chat_id, title, markdown_text, at_userids=None):
        """发送 markdown 消息"""
        import json
        token = self._get_access_token()
        msg_param = {"title": title, "text": markdown_text}
        if at_userids:
            msg_param["atUserIds"] = at_userids

        payload = {
            "robotCode": self.robot_code,
            "openConversationId": chat_id,
            "msgKey": "sampleMarkdown",
            "msgParam": json.dumps(msg_param, ensure_ascii=False),
        }
        resp = requests.post(
            "https://api.dingtalk.com/v1.0/robot/groupMessages/send",
            headers={"x-acs-dingtalk-access-token": token, "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        data = resp.json() if resp.text else {}
        if resp.status_code != 200 or data.get("code"):
            raise RuntimeError(f"发送失败 status={resp.status_code} resp={data}")
        return data

    def send_image(self, chat_id, image_bytes):
        """上传并发送图片"""
        import json
        media_id = self._upload_image(image_bytes)
        token = self._get_access_token()
        url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
        payload = {
            "robotCode": self.robot_code,
            "openConversationId": chat_id,
            "msgKey": "sampleImageMsg",
            "msgParam": json.dumps({"photoURL": media_id}, ensure_ascii=False),
        }
        resp = requests.post(
            url,
            headers={
                "x-acs-dingtalk-access-token": token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json() if resp.text else {}
        if resp.status_code != 200 or data.get("code"):
            raise RuntimeError(f"图片发送失败 status={resp.status_code} resp={data}")
        return data

    def _upload_image(self, image_bytes):
        """上传图片到钉钉媒体存储"""
        token = self._get_access_token()
        resp = requests.post(
            f"https://oapi.dingtalk.com/media/upload?access_token={token}&type=image",
            files={"media": ("table.png", image_bytes, "image/png")},
            timeout=30,
        )
        data = resp.json() if resp.text else {}
        if resp.status_code != 200 or data.get("errcode", 0) != 0:
            raise RuntimeError(f"图片上传失败 status={resp.status_code} resp={data}")
        return data["media_id"]

    def _get_access_token(self):
        """获取 access token（带缓存）"""
        now = time.time()
        if self._token_cache["token"] and self._token_cache["expire_at"] > now + 60:
            return self._token_cache["token"]

        url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
        resp = requests.post(
            url,
            json={"appKey": self.app_key, "appSecret": self.app_secret},
            timeout=10,
        )
        data = resp.json()
        if "accessToken" not in data:
            raise RuntimeError(f"获取 accessToken 失败: {data}")
        self._token_cache["token"] = data["accessToken"]
        self._token_cache["expire_at"] = now + int(data.get("expireIn", 7200))
        return self._token_cache["token"]
