# 周报工具 (Weekly Report CLI)

生活 / 工作 两个分类，自动按 ISO 周归档为 Markdown 文件，方便后续搜索、合并、或发到 IM。

零依赖 (Python 标准库)、按周归档、生活/工作分开、月度 + 年度汇总、AI 年度复盘、macOS 每周五自动弹通知。

## 文件结构

```
For_Codex/
├── weekly_report.py                       # 主脚本
├── README.md                              # 本文件
├── bin/
│   ├── notify_weekly_report.sh            # launchd 触发的脚本 (弹通知 + 开 Terminal)
│   ├── com.user.weekly-report.plist       # launchd 配置文件
│   ├── install_reminder.sh                # 一键安装 launchd
│   └── uninstall_reminder.sh              # 一键卸载 launchd
└── reports/
    └── 2026/
        ├── 2026-W30-life.md
        ├── 2026-W30-work.md
        ├── 2026-W30-combined.md   # combine 生成
        ├── 2026-07-summary.md     # summary 生成
        ├── 2026-07-summary.json
        ├── 2026-yearly.md         # yearly 生成
        ├── 2026-yearly.json
        └── 2026-recap.md          # recap --provider openai 生成 (有 API key 时)
```

## 命令

| 命令                                                                | 说明                                          |
| ------------------------------------------------------------------- | --------------------------------------------- |
| `python3 weekly_report.py new`                                     | 新建本周周报（默认），交互式输入              |
| `python3 weekly_report.py today`                                   | 显示今天是第几周、还剩几天                    |
| `python3 weekly_report.py list`                                    | 列出所有已生成的周报                          |
| `python3 weekly_report.py view YEAR WEEK`                          | 查看指定周的两份周报                          |
| `python3 weekly_report.py combine YEAR WEEK`                       | 把生活 + 工作合并为一份文件                   |
| `python3 weekly_report.py summary YEAR MONTH [--format md\|json]` | 生成月度汇总                                  |
| `python3 weekly_report.py yearly YEAR [--format md\|json]`        | 年度汇总 + 月度排行榜 + 下周计划追踪          |
| `python3 weekly_report.py quarter YEAR Q [--format md\|json]`       | 季度汇总 (Q=1-4, 复用 _track_plans)          |
| `python3 bin/weekly_report_web.py [--port 8765]`                      | 启动 Web UI (纯 stdlib, 无第三方依赖)        |
| `python3 weekly_report.py recap YEAR [--provider prompt\|openai]` | AI 年度复盘 (默认打印 prompt，可用 OpenAI 自动跑) |

```bash
# 速查
wr today                                          # 今天属于第几周
wr new                                            # 写本周周报
wr new --year 2026 --week 28                      # 补录历史周
wr summary 2026 7                                 # 月度汇总
wr summary 2026 7 --format json                   # JSON 模式
wr yearly 2026                                    # 年度汇总 + plan 追踪
wr yearly 2026 --format json                      # 年度 JSON
wr recap 2026                                     # 打印 prompt (粘到 ChatGPT / Claude)
wr recap 2026 --provider openai                   # 自动调 OpenAI (需 OPENAI_API_KEY)
```

## 录入交互

每次进入一个分类（工作 / 生活），会出现提示：

```
  [工作 #1] _
```

- **一行一条**，回车确认；**空行**结束当前分类
- **`:n`** 切换到「下周计划」
- **`:r`** 切换到「心得/反思」
- **`:q`** 提前结束当前分类
- **Ctrl+C** 中断整次录入（不会保存任何东西）

## 📊 月度汇总 (`summary`)

`wr summary 2026 7` 自动找出「周一落在 7 月」的 ISO 周 (W27 ~ W31)，逐周聚合，输出 Markdown 或 JSON。缺失周次单独提示，方便补录。

## 🗓️ 季度汇总 (`quarter`)

`wr quarter 2026 3` 是年度与月度之间的中间粒度：

- 季度定义: **Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec**
- 输出文件: `reports/2026/2026-Q3-quarterly.md` / `.json`
- 复用 `_track_plans`：跨周的下周计划追踪在季度内仍然有效
- 跟 yearly 一样的结构: 月度概览 + 工作 / 生活清单 + 心得反思 + plan 追踪 + 数据小计

```bash
wr quarter 2026 3                 # Q3 季度汇总
wr quarter 2026 3 --format json   # JSON 模式
wr quarter 2026 1                 # Q1 (1-3月)
wr quarter 2026 4                 # Q4 (10-12月)
```

适合做**季度 OKR 复盘**或**半年总结**时的中间粒度。

## 📅 年度汇总 (`yearly`)

`wr yearly 2026` 的功能：

- 📅 月度概览：每月条目数 / 覆盖周数
- 🏆 月度排行榜：🥇 工作最高产 / 🌿 生活最丰富
- 💼🌿 全年完成清单：按月 → 周 → 条目 三级组织
- 💡 心得 / 反思
- 🎯 **下周计划追踪**：自动判 ✅ 已完成 / ⏳ 仍然 pending（两层模糊匹配）

## 🤖 AI 年度复盘 (`recap`)

两个模式可选：

### 模式 1: prompt (默认, 零成本)

```bash
wr recap 2026
```

把这份提示词粘到 ChatGPT / Claude / Gemini 都行。

输出结构固定：

- 🌟 **年度亮点** (5-7 条) —— 引用具体 W##
- 📈 **成长 / 改进建议** (3-5 条) —— 可操作的下一步
- 🎯 **明年 3 个 SMART 目标** —— 至少 1 个生活类

### 模式 2: openai (一键自动跑)

```bash
export OPENAI_API_KEY=sk-...
wr recap 2026 --provider openai            # 用 gpt-4o-mini
wr recap 2026 --provider openai --model gpt-4o  # 切换模型
wr recap 2026 --provider openai --save my-recap.md  # 自定义输出路径
```

自动调用 OpenAI，结果保存到 `reports/2026/2026-recap.md`，同时打印到 stdout。

**没设置 API key 时**会友好提示如何设置 / 退回到 prompt 模式。

**网络错误时**给出明确诊断（API 错误码 / 是否需要代理）。

## ⏰ macOS 每周五 17:00 自动弹通知 (`bin/`)

零依赖 macOS 原生方案：launchd + AppleScript。

### 一键安装

```bash
bash ~/Downloads/mass/For_Codex/bin/install_reminder.sh
```

会做这些事：

1. 复制 plist 到 `~/Library/LaunchAgents/`
2. `plutil -lint` 校验 plist 语法
3. `launchctl load -w` 加载
4. 立刻生效，下个周五 17:00 触发

### 触发时它做的事

1. 弹 macOS 通知：「周末到了，用 wr new 写这周吧 📝」
2. 自动打开 Terminal，cd 到项目目录并准备好 `wr new` 命令，直接回车开始写

### 常用命令

```bash
# 立即触发 (不用等到下周五)
launchctl kickstart -k gui/$(id -u)/com.user.weekly-report

# 查看状态
launchctl list | grep weekly-report

# 看运行日志
tail -f /tmp/weekly-report-reminder.log

# 卸载
bash ~/Downloads/mass/For_Codex/bin/uninstall_reminder.sh
```

### 工作原理

`com.user.weekly-report.plist` 关键配置：

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Weekday</key>      <integer>6</integer>   <!-- Friday = 6 in launchd -->
    <key>Hour</key>         <integer>17</integer>
    <key>Minute</key>       <integer>0</integer>
</dict>
```

如果想改时间 / 改星期，直接编辑 plist 里的这三个 integer，然后 `launchctl unload` + `launchctl load -w`。

## 一键启动 (推荐)

把下面这行加到你的 `~/.zshrc`（或 `~/.bashrc`）里：

```sh
alias wr="python3 ~/Downloads/mass/For_Codex/weekly_report.py"
```

之后任何目录敲 `wr` 即可。

## 🌐 Web UI (本地浏览器)

启动:

```bash
python3 bin/weekly_report_web.py             # 默认 127.0.0.1:8765
python3 bin/weekly_report_web.py --port 9000 # 自定义端口
python3 bin/weekly_report_web.py --host 0.0.0.0  # 局域网可访问
```

浏览器打开 `http://127.0.0.1:8765` 看到主页, 含:

| 路由                          | 说明                                |
| ----------------------------- | ----------------------------------- |
| `GET /`                       | 主页 (本周 + 统计 + 最近记录)        |
| `GET /new`                    | 写周报表单 (工作 + 生活多个 textarea) |
| `POST /new`                   | 提交表单, 写入文件并跳转查看         |
| `GET /list`                   | 所有周报列表                        |
| `GET /view/<year>/<week>`     | 单周分开视图 (生活 / 工作两张卡片)   |
| `GET /combined/<year>/<week>` | 单周合并视图                        |
| `GET /summary/<year>/<month>` | 月度汇总 (Markdown 渲染成 HTML)      |
| `GET /quarter/<year>/<q>`     | 季度汇总                            |
| `GET /yearly/<year>`          | 年度汇总 + plan 追踪                |
| `GET /recap/<year>`           | AI 年度复盘的完整 prompt             |

### 设计要点

- **零第三方依赖**: 只用 `http.server` (stdlib)
- **Markdown 渲染**: 自写小引擎, 支持 h1-h4 / 列表 / 引用 / **粗体** / `代码` / 表格
- **响应式**: 移动端也能看
- **写作优先**: 主页大字展示本周 + 一键写周报按钮
- **汇总路由会自动重新生成**: 访问 `/yearly/2026` 会先调 cmd_yearly 确保最新

## 🎬 演示数据 (Demo)

第一次跑? 想看看汇总长什么样? 跑这个生成 5 周示例数据:

```bash
python3 bin/generate_demo.py            # 覆盖写入 W25-W29
python3 bin/generate_demo.py --keep     # 只填补缺失周, 不覆盖已有
```

**Demo 数据 persona**: Senior 工程师 + 新手爸爸 + 学 CISSP + 用 AI 工具 (跟你 W30 已有的真实记录风格一致). 跨周 plan 追踪**真实可命中**——W25 的「continue CISSP domain 2」会在 W26 完成, W26 的「design agent prototype」会在 W27 完成, 以此类推.

跑完之后:

```bash
wr list                     # 看到 W25-W30 共 6 周
wr summary 2026 7           # 7 月汇总, 看到工作 / 生活数据
wr quarter 2026 3           # Q3 汇总, plan 追踪有 5-6 条命中
wr yearly 2026              # 年度汇总, 11% 覆盖率
```

**不影响你已有的 W30 真实数据**, 只会添加 W25-W29 五周.

想清除 demo 数据? 直接 `rm reports/2026/2026-W2[5-9]-*.md` 即可.

## 设计选择

- **零依赖**：只用 Python 标准库，复制到任何机器都能跑
- **Markdown 输出**：方便配合 `grep` / `ripgrep` 做年终搜索
- **生活 / 工作 分文件**：避免合并时被同事看到私人部分
- **按 ISO 周归档**：跨年周（如 W01 的周一是去年 12-29）也归属正确

## ⚠️ 已知边界

- **跨月 ISO 周**：2026-W01 的周一可能是 2025-12-29。汇总按「周一落在哪个月份」归属。
- **下周计划追踪**：机器判 ✅ / ⏳ 是**辅助**——遇到误判就去 yearly.md 里翻原文定夺。
- **JSON 体积**：当月条目特别多时文件略大（万行级别才需要分页）。
- **Yearly 的空白年份**：如果一年中一行周报都没录，`wr yearly` 会直接报 "没有任何周报"。建议养成习惯：哪怕出差/休整那一周也写一条「本周休假，下周继续」保留节奏。
- **Plan 跨年追踪**：yearly 默认只跟踪当年内的 week 序列。
- **OpenAI API**：默认 base URL 是 `https://api.openai.com/v1/`。如果在国内或用第三方代理，需要修改源码里 `_recap_openai` 的 URL。
