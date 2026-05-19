#!/usr/bin/env python3
"""查询钉钉群列表和用户userid的工具脚本"""
import sys
import requests
sys.path.insert(0, '.')
from dingtalk import _get_access_token


def list_chats():
    """查询所有群聊列表"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/chat/list?access_token={token}"

    resp = requests.get(url)
    data = resp.json()

    if data.get("errcode") != 0:
        print(f"✗ 查询群列表失败: {data}")
        return []

    print(f"\n📋 群聊列表（共 {len(data.get('chatlist', []))} 个）：")
    print("-" * 80)
    for chat in data.get("chatlist", []):
        print(f"群名: {chat.get('name', 'N/A')}")
        print(f"ChatID: {chat.get('chatid', 'N/A')}")
        print(f"群主: {chat.get('owner', 'N/A')}")
        print("-" * 80)

    return data.get("chatlist", [])


def get_userid_by_mobile(mobile):
    """通过手机号查询userid"""
    token = _get_access_token()
    url = f"https://oapi.dingtalk.com/topapi/v2/user/getbymobile?access_token={token}"

    resp = requests.post(url, json={"mobile": mobile})
    data = resp.json()

    if data.get("errcode") != 0:
        print(f"✗ 查询失败 ({mobile}): {data}")
        return None

    userid = data.get("result", {}).get("userid")
    name = data.get("result", {}).get("name")
    print(f"✓ {name} ({mobile}): {userid}")
    return userid


def batch_query_userids():
    """批量查询TL的userid"""
    print("\n👥 查询TL的userid：")
    print("-" * 80)

    # 这里需要填入TL的手机号
    tl_phones = {
        "TL_A": "",
        "TL_B": "",
        "TL_C": "",
        "TL_D": "",
        "TL_E": "",
        "TL_F": "",
        "TL_G": "",
        "TL_H": "",
        "TL_I": "",
    }

    print("请提供TL的手机号，格式：姓名=手机号（一行一个）")
    print("示例：TL_A=13800138000")
    print("输入完成后按 Ctrl+D (Mac/Linux) 或 Ctrl+Z (Windows) 结束")
    print()

    results = {}
    try:
        while True:
            line = input().strip()
            if not line:
                continue
            if "=" in line:
                name, phone = line.split("=", 1)
                name = name.strip()
                phone = phone.strip()
                if name in tl_phones:
                    userid = get_userid_by_mobile(phone)
                    if userid:
                        results[name] = {"phone": phone, "userid": userid}
    except EOFError:
        pass

    print("\n" + "=" * 80)
    print("查询结果汇总：")
    print("=" * 80)
    for name, info in results.items():
        print(f'"{name}": {{"name": "{name}", "userid": "{info["userid"]}"}},')


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="查询钉钉群列表和用户userid")
    p.add_argument("action", choices=["chats", "users"], help="chats=查询群列表, users=查询用户userid")
    args = p.parse_args()

    if args.action == "chats":
        list_chats()
    elif args.action == "users":
        batch_query_userids()
