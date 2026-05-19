"""真实团队/TL 配置 — 复制本文件为 team_config_local.py 后填入真实值,team_config_local.py 已被 .gitignore 忽略"""

TEAM_CONFIG = {
    "团队名": {
        "groups": ["X组", "Y组"],
        "tl_map": {
            "X组": {"name": "TL真实姓名", "userid": "钉钉userid"},
            "Y组": {"name": "TL真实姓名", "userid": "钉钉userid"},
        },
        "schedule": {
            "phase1": "09:00",
            "phase2_3": ["11:30", "14:00", "16:00"],
        },
        "chatid": "钉钉群chatid",
    },
}
