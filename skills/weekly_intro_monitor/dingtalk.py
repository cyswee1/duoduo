#!/usr/bin/env python3
"""钉钉企业内部应用API封装 — 凭证到位后启用"""
import requests

from config import DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET


def _get_access_token():
    """获取钉钉企业内部应用access_token"""
    if not DINGTALK_CLIENT_ID or not DINGTALK_CLIENT_SECRET:
        raise RuntimeError("钉钉凭证未配置（DINGTALK_CLIENT_ID / DINGTALK_CLIENT_SECRET）")

    url = "https://oapi.dingtalk.com/gettoken"
    resp = requests.get(url, params={
        "appkey": DINGTALK_CLIENT_ID,
        "appsecret": DINGTALK_CLIENT_SECRET,
    })
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"获取access_token失败: {data}")
    return data["access_token"]


def send_text(chatid, content, at_users=None):
    """发送文本消息到群"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/chat/send?access_token={token}"

    msg = {
        "chatid": chatid,
        "msg": {
            "msgtype": "text",
            "text": {"content": content},
        },
    }

    resp = requests.post(url, json=msg)
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"发送文本消息失败: {data}")
    return data


def send_markdown(chatid, title, content, at_users=None):
    """发送markdown消息到群"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/chat/send?access_token={token}"

    msg = {
        "chatid": chatid,
        "msg": {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content,
            },
        },
    }

    resp = requests.post(url, json=msg)
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"发送markdown消息失败: {data}")
    return data


def send_image(chatid, media_id):
    """发送图片消息到群（需先上传媒体文件获取media_id）"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/chat/send?access_token={token}"

    msg = {
        "chatid": chatid,
        "msg": {
            "msgtype": "image",
            "image": {"media_id": media_id},
        },
    }

    resp = requests.post(url, json=msg)
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"发送图片消息失败: {data}")
    return data


def upload_media(file_path, media_type="image"):
    """上传媒体文件到钉钉，返回media_id"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/media/upload?access_token={token}&type={media_type}"

    with open(file_path, "rb") as f:
        resp = requests.post(url, files={"media": f})

    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"上传媒体文件失败: {data}")
    return data["media_id"]


def read_multidimensional_table(table_id, sheet_name):
    """读取钉钉多维表格数据，返回 {小组名: {字段: 值}} 字典"""
    token = _get_access_token()

    # 钉钉多维表格API（需确认具体endpoint和参数）
    # 文档: https://open.dingtalk.com/document/orgapp/read-data-from-multidimensional-tables
    url = f"https://api.dingtalk.com/v1.0/doc/spaces/sheets/{table_id}/ranges/{sheet_name}"
    headers = {
        "x-acs-dingtalk-access-token": token,
        "Content-Type": "application/json",
    }

    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"读取多维表格失败: {resp.status_code} {resp.text}")

    data = resp.json()
    # 解析为 {小组名: {字段: 值}} 格式
    # 具体解析逻辑需根据实际返回结构调整
    result = {}
    records = data.get("records", data.get("values", []))
    for record in records:
        fields = record.get("fields", record)
        group = fields.get("小组", "")
        if group:
            result[group] = fields

    return result
