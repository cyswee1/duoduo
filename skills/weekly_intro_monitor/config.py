import os
from pathlib import Path

SKILL_DIR = Path(__file__).parent
BI_SKILL_DIR = SKILL_DIR.parent / "bi_skill"

# 团队和 TL 配置 — 真实姓名/userid/chatid 通过本地未入库的 team_config_local.py 提供
# 仓库内只保留结构示例,使用前请复制 team_config_local.example.py 为 team_config_local.py 并填入真实值
try:
    from team_config_local import TEAM_CONFIG  # type: ignore
except ImportError:
    TEAM_CONFIG = {
        "团队A": {
            "groups": ["A1组", "A2组"],
            "tl_map": {
                "A1组": {"name": "TL姓名占位", "userid": ""},
                "A2组": {"name": "TL姓名占位", "userid": ""},
            },
            "schedule": {
                "phase1": "09:00",
                "phase2_3": ["11:30", "14:00", "16:00"],
            },
            "chatid": "",
        },
    }

TARGET_POOLS = ["M1-M3（首消）", "续费带R", "服务池"]

PROGRESS_THRESHOLD = 0.8
CALL_LOW_THRESHOLD = 0.5
ZERO_FOLLOWUP_WARN = True
MIN_CALL_WITH_ZERO_CONVERSION = 10

# 钉钉企业内部应用凭证 — 从环境变量读取,不要硬编码
DINGTALK_APP_ID = os.environ.get("DINGTALK_APP_ID", "")
DINGTALK_CLIENT_ID = os.environ.get("DINGTALK_CLIENT_ID", "")
DINGTALK_CLIENT_SECRET = os.environ.get("DINGTALK_CLIENT_SECRET", "")
DINGTALK_TABLE_ID = os.environ.get("DINGTALK_TABLE_ID", "")
DINGTALK_TABLE_SHEET = os.environ.get("DINGTALK_TABLE_SHEET", "")

BI_REPORT_PROGRESS = "转介绍益智业绩播报_LP维度_末次渠道"
BI_REPORT_FOLLOWUP = "思维转介绍过程跟进报表_末次渠道"

OUTPUT_DIR = Path.home() / "Downloads"
