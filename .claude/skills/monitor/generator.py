"""批量生成器 — 从 scenarios/registry.yaml 生成各场景的可运行配置文件。

用法:
    python generator.py                    # 生成所有场景
    python generator.py --scenario renewal # 只生成指定场景
"""
import sys
import copy
from pathlib import Path

import yaml


REGISTRY_PATH = Path(__file__).parent / "scenarios" / "registry.yaml"
OUTPUT_DIR = Path(__file__).parent / "generated"


def load_registry(path=None):
    path = path or REGISTRY_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_scenario_config(shared, scenario_key, scenario):
    """合并 shared + scenario 配置，输出完整的可运行 YAML 结构"""
    cfg = {
        "name": scenario["name"],
        "description": scenario["description"],
        "secrets_file": shared["secrets_file"],
    }

    # teams: 合并 shared teams + scenario schedule
    teams = copy.deepcopy(shared["teams"])
    for team_name, team_cfg in teams.items():
        sched = scenario.get("schedule", {}).get(team_name, {})
        team_cfg["schedule"] = sched
    cfg["teams"] = teams

    # datasources
    datasources = {}

    # smartbi (always needed for BI reports)
    smartbi_cfg = copy.deepcopy(shared["smartbi"])
    smartbi_cfg["reports"] = scenario["reports"]
    datasources["smartbi"] = smartbi_cfg

    # dingtalk_report (target source)
    target_src = copy.deepcopy(shared["target_source"])
    target_src["fields"] = scenario["target_fields"]
    if "pool_name_mapping" in scenario:
        target_src["pool_name_mapping"] = scenario["pool_name_mapping"]
    if "section_priority" in scenario:
        target_src["section_priority"] = scenario["section_priority"]
    datasources["dingtalk_report"] = target_src

    cfg["datasources"] = datasources

    # notable (港澳多维表格)
    if "notable" in shared:
        cfg["datasources"]["notable"] = copy.deepcopy(shared["notable"])

    # phases
    cfg["phases"] = copy.deepcopy(scenario["phases"])

    # notifier
    cfg["notifier"] = copy.deepcopy(shared["notifier"])

    # globals
    cfg["globals"] = copy.deepcopy(shared["globals"])

    return cfg


def generate_all(registry, scenario_filter=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    shared = registry["shared"]
    scenarios = registry["scenarios"]

    generated = []
    for key, scenario in scenarios.items():
        if scenario_filter and key != scenario_filter:
            continue

        cfg = build_scenario_config(shared, key, scenario)
        output_path = OUTPUT_DIR / f"{scenario['name']}.yaml"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# 自动生成 — 源自 scenarios/registry.yaml [{key}]\n")
            f.write(f"# 运行: python engine.py {output_path.relative_to(output_path.parent.parent)} <team> <phase>\n\n")
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        generated.append(output_path)
        print(f"  生成: {output_path}")

    return generated


def main():
    scenario_filter = None
    if "--scenario" in sys.argv:
        idx = sys.argv.index("--scenario")
        if idx + 1 < len(sys.argv):
            scenario_filter = sys.argv[idx + 1]

    registry = load_registry()
    print(f"加载注册表: {REGISTRY_PATH}")
    print(f"场景数: {len(registry['scenarios'])}")
    print()

    generated = generate_all(registry, scenario_filter)
    print(f"\n完成，共生成 {len(generated)} 个配置文件")


if __name__ == "__main__":
    main()
