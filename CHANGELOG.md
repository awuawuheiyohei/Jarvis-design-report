# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- GitHub Pages 部署 Web UI
- 对接 Strava / Apple Health 自动填充生活周报
- Web UI 加统计图表 (每周条目数折线图)

## [1.0.0] - 2026-08-01

### Added
- **CLI 工具** `weekly_report.py` — 9 个子命令:
  - `new` / `list` / `view` / `combine` — 基础读写
  - `today` — 快速看今天是第几周
  - `summary YEAR MONTH` — 月度汇总
  - `quarter YEAR Q` — 季度汇总 (Q1-Q4)
  - `yearly YEAR` — 年度汇总 + 下周计划追踪 (两层模糊匹配)
  - `recap YEAR` — AI 年度复盘 (默认打印 prompt, 可选 OpenAI 自动跑)
- **生活 / 工作 分开存储**: `reports/YEAR/YEAR-W##-work.md` / `-life.md`
- **按 ISO 周归档**: 跨年周 (W01) 也归属正确
- **macOS 每周五 17:00 弹通知** (`bin/install_reminder.sh` + `notify_weekly_report.sh` + `com.user.weekly-report.plist`)
- **Web UI** (`bin/weekly_report_web.py`) — 纯 stdlib `http.server`, 10 个路由, 自写 Markdown 渲染引擎
- **Demo 数据生成器** (`bin/generate_demo.py`) — 5 周 (W25-W29) 真实风格示例数据
- **零第三方依赖**: 只用 Python 标准库

### Design choices
- 生活 / 工作 分文件存储, 合并时可选择性
- Markdown 输出方便 `grep` / `ripgrep` 搜索
- 所有汇总幂等, 可重复跑
- 周一归属月 (跨月 ISO 周按周一所在月归类)

### Known caveats
- 跨月 ISO 周 (如 2026-W01 的周一是 2025-12-29) 归周一所在月
- Plan 追踪是辅助判断, 模糊匹配可能漏/误, 重要事请手动核对
- Web UI 启动需要本地端口 (sandbox 默认不允许)
- OpenAI provider 默认 base URL 是 `api.openai.com`, 国内用需要换 gateway
