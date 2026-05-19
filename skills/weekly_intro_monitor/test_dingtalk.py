#!/usr/bin/env python3
"""测试钉钉凭证并获取群列表、用户信息"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dingtalk import _get_access_token
import requests


def test_access_token():
    """测试获取access_token"""
    print("=" * 60)
    print("测试钉钉凭证")
    print("=" * 60)
    try:
        token = _get_access_token()
        print(f"✓ access_token 获取成功: {token[:20]}...")
        return token
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        return None


def get_user_by_name(token, name):
    """根据姓名搜索用户userid"""
    print(f"\n搜索用户: {name}")
    url = f"https://oapi.dingtalk.com/topapi/v2/user/search?access_token={token}"
    resp = requests.post(url, json={"query_word": name, "size": 10})
    data = resp.json()

    if data.get("errcode") != 0:
        print(f"  ✗ 搜索失败: {data}")
        return None

    users = data.get("result", {}).get("list", [])
    if not users:
        print(f"  未找到用户")
        return None

    print(f"  找到 {len(users)} 个用户:")
    for u in users:
        print(f"    - {u.get('name')} (userid: {u.get('userid')})")

    return users[0].get("userid") if users else None


def search_all_tls(token, tl_names):
    """批量搜索所有TL的userid"""
    print("\n" + "=" * 60)
    print("搜索所有TL的userid")
    print("=" * 60)

    result = {}
    for name in tl_names:
        userid = get_user_by_name(token, name)
        if userid:
            result[name] = userid

    print("\n汇总结果:")
    for name, userid in result.items():
        print(f"  {name}: {userid}")

    return result


def list_chats(token):
    """列出应用可见的群会话"""
    print("\n" + "=" * 60)
    print("获取群会话列表")
    print("=" * 60)

    # 方法1: 获取会话列表（需要会话权限）
    url = f"https://oapi.dingtalk.com/chat/list?access_token={token}"
    resp = requests.get(url)
    data = resp.json()

    if data.get("errcode") == 0:
        chats = data.get("chatlist", [])
        print(f"找到 {len(chats)} 个群会话:")
        for chat in chats:
            print(f"  - {chat.get('name')} (chatid: {chat.get('chatid')})")
        return chats
    else:
        print(f"✗ 获取失败: {data}")
        print("\n可能原因:")
        print("1. 应用未开通「群会话管理」权限")
        print("2. 需要先创建群会话或将应用添加到现有群")

    # 方法2: 创建测试群
    print("\n" + "=" * 60)
    print("或者，可以通过API创建群会话")
    print("=" * 60)
    print("示例代码:")
    print("""
url = f"https://oapi.dingtalk.com/chat/create?access_token={token}"
data = {
    "name": "美澳团队-转介绍监控",
    "owner": "管理员userid",
    "useridlist": ["TL1的userid", "TL2的userid", ...]
}
resp = requests.post(url, json=data)
# 返回的 chatid 就是群ID
""")
    return []


if __name__ == "__main__":
    token = test_access_token()
    if not token:
        sys.exit(1)

    # 尝试获取群列表
    chats = list_chats(token)

    print("\n" + "=" * 60)
    print("获取 chatid 的其他方法")
    print("=" * 60)
    print("1. 如果群已存在，让群主:")
    print("   - 打开群 → 群设置 → 群管理 → 查看群ID")
    print("   - 或在钉钉管理后台 → 工作台 → 群管理 中查找")
    print("\n2. 如果需要创建新群，可以:")
    print("   - 通过钉钉PC端手动创建群")
    print("   - 或使用上面的API创建群（需要提供管理员和成员的userid）")
    print("\n3. 临时方案：先用 --dry-run 模式测试数据处理逻辑")
    print("   不发送钉钉消息，只输出到终端")
