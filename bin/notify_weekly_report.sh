#!/usr/bin/env bash
# notify_weekly_report.sh
# launchd 每周五 17:00 触发。弹 macOS 通知 + 打开 Terminal 准备 wr new。

set -euo pipefail

PROJECT="/Users/jiangwenrui/Downloads/mass/For_Codex"
WR_CMD="python3 ${PROJECT}/weekly_report.py new"

# 1. macOS 通知
osascript <<EOF
display notification "周末到了，用 wr new 写这周吧 📝" \
    with title "Weekly Report" \
    subtitle "周报时间" \
    sound name "Pop"
EOF

# 2. 打开 Terminal，cd 到项目并准备运行 wr new
osascript <<EOF
tell application "Terminal"
    activate
    do script "cd ${PROJECT} && ${WR_CMD}"
end tell
EOF
