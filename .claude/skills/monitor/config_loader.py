"""配置加载器 — 从 YAML 读取监控任务的全部参数。"""
import os
import yaml
from pathlib import Path
from datetime import date, timedelta


ENV_SECRETS_FILE = "MONITOR_SECRETS_FILE"


def load_config(config_path):
    """加载并预处理 YAML 配置"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    _resolve_templates(cfg)
    return cfg


def _resolve_templates(cfg):
    """解析模板变量（如 {this_monday}）"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    cfg["_resolved"] = {
        "this_monday": monday.strftime("%Y-%m-%d"),
        "today": today.strftime("%Y-%m-%d"),
    }


def get_secrets_loader(cfg):
    """根据配置返回凭证加载函数"""
    env_path = os.environ.get(ENV_SECRETS_FILE, "").strip()
    secrets_path = env_path or cfg.get("secrets_file", "~/.claude/secrets/monitor.env")
    secrets_file = Path(secrets_path).expanduser()
    if not secrets_file.exists():
        raise RuntimeError(f"凭证文件不存在: {secrets_file}")

    cache = {}

    def _load():
        if cache:
            return cache
        for line in secrets_file.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                cache[k.strip()] = v.strip()
        return cache

    return _load
