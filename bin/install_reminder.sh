#!/usr/bin/env bash
# install_reminder.sh - 一键安装 launchd 周五提醒
set -euo pipefail

PROJECT="/Users/jiangwenrui/Downloads/mass/For_Codex"
SRC="${PROJECT}/bin/com.user.weekly-report.plist"
DST="${HOME}/Library/LaunchAgents/com.user.weekly-report.plist"

mkdir -p "${HOME}/Library/LaunchAgents"

# 如果已经装过，先卸掉再覆盖
if launchctl list 2>/dev/null | grep -q "com.user.weekly-report"; then
    echo "↻ 检测到已加载的任务，先卸载..."
    launchctl unload "${DST}" 2>/dev/null || true
fi

cp "${SRC}" "${DST}"
echo "✅ plist 已复制到 ${DST}"

# 校验 plist
if plutil -lint "${DST}"; then
    echo "✅ plist 语法 OK"
else
    echo "❌ plist 语法错误"
    exit 1
fi

# 加载
launchctl load -w "${DST}"
echo "✅ launchd 已加载"

echo ""
echo "🎉 完成！下个周五 17:00 会自动弹通知。"
echo ""
echo "常用命令："
echo "  立即触发:  launchctl kickstart -k gui/$(id -u)/com.user.weekly-report"
echo "  查看状态:  launchctl list | grep weekly-report"
echo "  卸载:      bash ${PROJECT}/bin/uninstall_reminder.sh"
echo "  看日志:    tail -f /tmp/weekly-report-reminder.log"
