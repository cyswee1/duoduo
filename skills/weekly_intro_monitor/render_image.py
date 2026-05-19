#!/usr/bin/env python3
"""将业绩播报数据渲染为图片"""
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import datetime
from pathlib import Path
import pandas as pd

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False


def render_progress_table(results, lagging, team, output_path=None):
    """
    将业绩播报数据渲染为表格图片

    Args:
        results: 计算结果列表
        lagging: 落后的小组列表
        team: 团队名称
        output_path: 输出路径，默认为临时文件

    Returns:
        图片文件路径
    """
    if output_path is None:
        output_path = Path.home() / "Downloads" / f"业绩播报_{team}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    # 创建图表 - 增加高度以容纳分组表头
    fig, ax = plt.subplots(figsize=(16, len(results) * 0.6 + 4))
    ax.axis('tight')
    ax.axis('off')

    # 准备表格数据
    headers = ['团队/小组', '负责人', '今日例子\n数', '今日例子\n目标', '今日达标\n率',
               '海外转介\n绍例子目\n标', '全体带海\n外例子数', '例子达成\n率-月度', 'GAP例子\n量']
    table_data = []

    for r in results:
        today_rate_str = f"{r['today_completion_rate']:.2%}"
        monthly_rate_str = f"{r['monthly_completion_rate']:.2%}"
        row = [
            r['group'],
            r['tl'],
            f"{r['today_count']:.0f}",
            f"{r['today_target']:.0f}",
            today_rate_str,
            f"{r['monthly_target']:.0f}",
            f"{r['total_count']:.0f}",
            monthly_rate_str,
            f"{r['gap']}"
        ]
        table_data.append(row)

    # 创建表格
    table = ax.table(
        cellText=table_data,
        colLabels=headers,
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )

    # 设置表格样式
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.2)

    # 设置表头样式 - 按照Excel原始格式
    # 0-1列：浅蓝灰色（团队/小组、负责人）
    for i in range(2):
        cell = table[(0, i)]
        cell.set_facecolor('#D9E2F3')
        cell.set_text_props(weight='bold', color='black', fontsize=9)

    # 2-4列：浅黄色（今日例子数、今日例子目标、今日达标率）
    for i in range(2, 5):
        cell = table[(0, i)]
        cell.set_facecolor('#FFF2CC')
        cell.set_text_props(weight='bold', color='black', fontsize=9)

    # 5-8列：浅绿色（海外转介绍例子目标、全体带海外例子数、例子达成率-月度、GAP例子量）
    for i in range(5, 9):
        cell = table[(0, i)]
        cell.set_facecolor('#E2EFDA')
        cell.set_text_props(weight='bold', color='black', fontsize=9)

    # 设置数据行样式
    for i, r in enumerate(results, start=1):
        # 所有单元格统一字体大小
        for j in range(9):
            cell = table[(i, j)]
            cell.set_text_props(fontsize=9)

        # 例子达成率-月度列使用色阶（第7列，索引7）
        monthly_rate_cell = table[(i, 7)]
        rate = r['monthly_completion_rate']

        # 使用Excel的色阶：绿色(高) -> 黄色(中) -> 橙色 -> 红色(低)
        if rate >= 0.7:
            # 70%以上：绿色
            monthly_rate_cell.set_facecolor('#92D050')
        elif rate >= 0.5:
            # 50-70%：黄绿色
            monthly_rate_cell.set_facecolor('#FFFF00')
        elif rate >= 0.4:
            # 40-50%：黄色
            monthly_rate_cell.set_facecolor('#FFD966')
        elif rate >= 0.3:
            # 30-40%：橙色
            monthly_rate_cell.set_facecolor('#F4B183')
        else:
            # <30%：红色
            monthly_rate_cell.set_facecolor('#FF6666')

    # 添加标题
    title = f"转介绍业绩进度播报 - {team}团队\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    plt.title(title, fontsize=13, weight='bold', pad=20)

    # 保存图片
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return str(output_path)


def render_followup_warning(pool_results, team, output_path=None):
    """
    将外呼跟进预警数据渲染为图片（按池子分组显示完整数据）

    Args:
        pool_results: 按池子分组的结果字典
        team: 团队名称
        output_path: 输出路径

    Returns:
        图片文件路径
    """
    if output_path is None:
        output_path = Path.home() / "Downloads" / f"外呼预警_{team}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    # 计算总行数（每个池子：标题行 + 表头行 + 数据行）
    total_rows = sum(2 + len(items) for items in pool_results.items())

    # 创建图表
    fig, ax = plt.subplots(figsize=(20, total_rows * 0.45 + 1))
    ax.axis('off')

    # 准备表格数据
    table_data = []

    # 按池子组织数据
    for pool_name, items in pool_results.items():
        # 池子标题行
        pool_title_row = [pool_name, '', '', '', '', '', '', '', '', '']
        table_data.append(pool_title_row)

        # 表头行（不换行）
        if pool_name == "续费带R":
            header_row = ['小组', '学员数', '外呼跟进率', '外呼有效跟进率', '综合有效跟进率',
                         '生均外呼次数', '续费带R数', '带R效率', '秒挂占比', '今日跟进目标']
        else:
            header_row = ['小组', '学员数', '外呼跟进率', '外呼有效跟进率', '综合有效跟进率',
                         '生均外呼次数', '带R数', '带R效率', '秒挂占比', '今日跟进目标']
        table_data.append(header_row)

        # 数据行
        for item in items:
            row = [
                item['group'],
                f"{int(item['student_count'])}",
                f"{item['call_rate']:.2%}",
                f"{item['effective_rate']:.2%}",
                f"{item['comprehensive_rate']:.2%}",
                f"{item['avg_calls']:.2f}",
                f"{item['带R数']}" if item['带R数'] > 0 else '',
                f"{item['带R效率']:.2%}" if item['带R效率'] > 0 else '',
                f"{item['秒挂占比']:.2%}" if item['秒挂占比'] > 0 else '',
                ''  # 今日跟进目标
            ]
            table_data.append(row)

    # 创建表格
    table = ax.table(
        cellText=table_data,
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )

    # 设置表格样式
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)

    # 设置样式
    row_idx = 0
    for pool_name, items in pool_results.items():
        # 池子标题行 - 深蓝色背景，白色文字，合并单元格效果
        # 只在第一个单元格显示文字，其他单元格设置相同背景色
        for j in range(10):
            cell = table[(row_idx, j)]
            cell.set_facecolor('#2E5090')
            if j == 0:
                cell.set_text_props(weight='bold', color='white', fontsize=11, ha='center')
            else:
                # 清空其他单元格的文字，只保留背景色
                cell.get_text().set_text('')
                cell.set_text_props(color='white')

        # 手动合并单元格效果：隐藏边框
        for j in range(1, 10):
            cell = table[(row_idx, j)]
            cell.set_edgecolor('#2E5090')

        row_idx += 1

        # 表头行 - 深蓝色背景，白色文字
        for j in range(10):
            cell = table[(row_idx, j)]
            cell.set_facecolor('#2E5090')
            cell.set_text_props(weight='bold', color='white', fontsize=9)
        row_idx += 1

        # 数据行
        for item in items:
            # 外呼跟进率列（索引2）- 应用颜色规则
            call_rate_cell = table[(row_idx, 2)]
            call_rate = item['call_rate']
            if call_rate < 0.6:
                call_rate_cell.set_facecolor('#FF9999')  # 浅红色
            elif call_rate < 0.9:
                call_rate_cell.set_facecolor('#FFEB9C')  # 浅黄色
            else:
                call_rate_cell.set_facecolor('#C6EFCE')  # 浅绿色

            # 综合有效跟进率列（索引4）- 应用颜色规则
            comp_rate_cell = table[(row_idx, 4)]
            comp_rate = item['comprehensive_rate']
            if comp_rate < 0.4:
                comp_rate_cell.set_facecolor('#FF9999')  # 浅红色
            elif comp_rate < 0.7:
                comp_rate_cell.set_facecolor('#FFEB9C')  # 浅黄色
            else:
                comp_rate_cell.set_facecolor('#C6EFCE')  # 浅绿色

            row_idx += 1

    # 添加标题
    title = f"转介绍外呼做工监控 - {team}团队\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    plt.title(title, fontsize=14, weight='bold', pad=20)

    # 保存图片
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()

    return str(output_path)
