# HTML 模板说明

`templates/dashboard.html` 是后端监控项目预留的静态看板模板。当前主流程主要把结果渲染成图片并推送到钉钉；如果后续需要把监控结果沉淀为网页、日报或归档页面，可以复用这个模板。

## 使用方式

模板通过占位符注入数据，生成完整 HTML 文件：

```python
html = template
html = html.replace("{{TITLE}}", title)
html = html.replace("{{TEAM}}", team)
html = html.replace("{{PHASE}}", phase)
html = html.replace("{{UPDATED_AT}}", updated_at)
html = html.replace("{{TOTAL_COUNT}}", str(total_count))
html = html.replace("{{OK_COUNT}}", str(ok_count))
html = html.replace("{{WARN_COUNT}}", str(warn_count))
html = html.replace("{{TABLE_HEADER}}", table_header)
html = html.replace("{{TABLE_ROWS}}", table_rows)
html = html.replace("{{EMPTY_TEXT}}", empty_text)
```

## 占位符说明

| 占位符 | 含义 | 示例 |
| --- | --- | --- |
| `{{TITLE}}` | 页面标题 | `进度监控日报` |
| `{{TEAM}}` | 团队名 | `团队A` |
| `{{PHASE}}` | 阶段名 | `phase2` |
| `{{UPDATED_AT}}` | 更新时间 | `2026-05-27 10:30` |
| `{{TOTAL_COUNT}}` | 监控项总数 | `12` |
| `{{OK_COUNT}}` | 达标项数量 | `9` |
| `{{WARN_COUNT}}` | 预警项数量 | `3` |
| `{{TABLE_HEADER}}` | 表格表头 HTML | `<tr><th>小组</th><th>状态</th></tr>` |
| `{{TABLE_ROWS}}` | 表格行 HTML | `<tr><td>团队A-1组</td><td>达标</td></tr>` |
| `{{EMPTY_TEXT}}` | 无数据提示 | `暂无预警` |

## 输出建议

- 本地调试时可输出到 `globals.output_dir`。
- 如果要上传到静态站点，生成前要确认不包含真实姓名、手机号、学员信息、内部链接或 token。
- 如果只是推送钉钉图片，不需要使用该模板。
