#!/usr/bin/env bash
# uninstall_reminder.sh - 卸载 launchd 周五提醒
set -euo pipefail

DST="${HOME}/Library/LaunchAgents/com.user.weekly-report.plist"

if launchctl list 2>/dev/null | grep -q "com.user.weekly-report"; then
    launchctl unload "${DST}" 2>/dev/null || true
    echo "✅ 已从 launchd 卸载"
fi

if [[ -f "${DST}" ]]; then
    rm "${DST}"
    echo "✅ 已删除 ${DST}"
else
    echo "(plist 文件本就不存在)"
fi

echo "🎉 卸载完成。"
