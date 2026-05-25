"""表格图片渲染器 — 参数化版本。"""
import io
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties


def _get_cjk_font():
    """获取系统中可用的中文字体"""
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return FontProperties(fname=p)
    return FontProperties()


class TableRenderer:
    """参数化的表格图片渲染器"""

    def __init__(self, render_config):
        """
        Args:
            render_config: table_render 配置块
        """
        self.config = render_config
        self.font = _get_cjk_font()

    def render_progress_table(self, team, results):
        """渲染业绩进度表格

        Args:
            team: 团队名
            results: list[dict] 小组维度数据

        Returns:
            io.BytesIO: PNG 图片字节流
        """
        headers = self.config["headers"]
        rows = []
        for r in results:
            rows.append([
                r["group"],
                r["tl"],
                f"{r['today_target']:.0f}",
                f"{r['today_count']:.0f}",
                f"{r['today_completion_rate']:.0%}",
                f"{r['monthly_target']:.0f}",
                f"{r['total_count']:.0f}",
                f"{r['monthly_completion_rate']:.0%}",
                str(r["gap"]),
            ])

        title = self.config["title_template"].format(team=team)
        return self._render_table(title, headers, rows, results, self.config["color_rules"])

    def render_followup_table(self, team, warnings_per_group):
        """渲染外呼跟进表格

        Args:
            team: 团队名
            warnings_per_group: {group: [{pool, rate, target, status, gap}, ...]}

        Returns:
            io.BytesIO: PNG 图片字节流
        """
        headers = self.config["headers"]
        rows = []
        row_data = []
        for group, items in warnings_per_group.items():
            for item in items:
                rate_str = f"{item['rate']:.2%}" if item["rate"] is not None else "无数据"
                target_str = f"{item['target']:.0%}"
                if item["status"] == "未达标":
                    status_str = f"差距 {item['gap']:.2%}"
                else:
                    status_str = item["status"]
                rows.append([group, item["pool"], rate_str, target_str, status_str])
                row_data.append(item)

        if not rows:
            return None

        title = self.config["title_template"].format(team=team)
        return self._render_table(title, headers, rows, row_data, self.config["color_rules"])

    def _render_table(self, title, headers, rows, row_data, color_rules):
        """通用表格渲染"""
        n_rows = len(rows)
        n_cols = len(headers)
        fig_width = max(10, n_cols * 1.3)
        fig_height = max(2.0, 0.6 + n_rows * 0.5)

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis("off")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        ax.set_title(f"{title}\n更新时间：{now_str}",
                     fontproperties=self.font, fontsize=13, pad=12, loc="center")

        table = ax.table(
            cellText=rows,
            colLabels=headers,
            loc="center",
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.0, 1.6)

        for (row_idx, col_idx), cell in table.get_celld().items():
            cell.set_text_props(fontproperties=self.font)
            if row_idx == 0:
                cell.set_facecolor("#4472C4")
                cell.set_text_props(color="white", weight="bold", fontproperties=self.font)
            else:
                cell.set_facecolor("#F2F2F2" if row_idx % 2 == 0 else "white")
                # 应用颜色规则
                self._apply_color_rules(cell, row_idx, col_idx, row_data, color_rules)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _apply_color_rules(self, cell, row_idx, col_idx, row_data, color_rules):
        """应用颜色规则"""
        if row_idx == 0:
            return
        data_idx = row_idx - 1
        if data_idx >= len(row_data):
            return

        for rule in color_rules:
            if rule["column_index"] != col_idx:
                continue

            condition = rule["condition"]
            color = rule["color"]

            # 简单条件解析
            if isinstance(row_data[data_idx], dict):
                data = row_data[data_idx]
                # 进度表：检查数值条件
                if "< 0.8" in condition and "today_completion_rate" in data:
                    if data["today_completion_rate"] < 0.8:
                        cell.set_text_props(color="red", weight="bold", fontproperties=self.font)
                elif "> 0" in condition and "gap" in data:
                    if data["gap"] > 0:
                        cell.set_text_props(color="red", weight="bold", fontproperties=self.font)
                # 跟进表：检查状态
                elif "status == '未达标'" in condition and data.get("status") == "未达标":
                    cell.set_text_props(color="red", weight="bold", fontproperties=self.font)
