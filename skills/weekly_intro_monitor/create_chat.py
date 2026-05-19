#!/usr/bin/env python3
"""创建钉钉群会话"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dingtalk import _get_access_token
import requests


def create_chat(token, name, owner_userid, member_userids):
    """创建群会话"""
    url = f"https://oapi.dingtalk.com/chat/create?access_token={token}"
    data = {
        "name": name,
        "owner": owner_userid,
        "useridlist": member_userids,
    }

    resp = requests.post(url, json=data)
    result = resp.json()

    if result.get("errcode") == 0:
        chatid = result.get("chatid")
        print(f"✓ 群创建成功")
        print(f"  群名: {name}")
        print(f"  chatid: {chatid}")
        return chatid
    else:
        print(f"✗ 创建失败: {result}")
        return None


if __name__ == "__main__":
    print("注意：创建群需要提供管理员和成员的 userid")
    print("如果没有 userid，建议先用 --dry-run 模式测试\n")

    token = _get_access_token()
    print(f"✓ access_token 获取成功\n")

    # 示例：创建美澳团队监控群
    # owner_userid = "你的userid"  # 需要替换
    # member_userids = ["TL_A的userid", "TL_B的userid", ...]  # 需要替换

    # chatid = create_chat(token, "美澳团队-转介绍监控", owner_userid, member_userids)

    print("=" * 60)
    print("临时方案：先测试数据处理逻辑")
    print("=" * 60)
    print("运行命令:")
    print("  python3 monitor.py phase2 --team 美澳 --dry-run --force")
    print("\n这会下载BI报表并计算进度，但不发送钉钉消息")
    print("等 chatid 配置好后再去掉 --dry-run 参数")
