#!/bin/bash
# 关闭用于 WSJ 抓取的 9222 调试 Chrome

set -euo pipefail

USER_DATA_DIR="$HOME/.wsj_chrome_profile"
PID_FILE="$USER_DATA_DIR/chrome-debug-9222.pid"
DEBUG_URL="http://localhost:9222/json/version"
PATTERN="--remote-debugging-port=9222.*--user-data-dir=$USER_DATA_DIR"

stopped=0

# 1) 优先按 PID 文件关闭
if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
        stopped=1
    fi
fi

# 2) 兜底：按参数匹配关闭所有调试 Chrome
pids="$(pgrep -f "$PATTERN" 2>/dev/null || true)"
if [ -n "$pids" ]; then
    kill $pids >/dev/null 2>&1 || true
    stopped=1
fi

# 等待优雅退出
sleep 1

# 3) 仍未退出则强制杀掉
still_pids="$(pgrep -f "$PATTERN" 2>/dev/null || true)"
if [ -n "$still_pids" ]; then
    kill -9 $still_pids >/dev/null 2>&1 || true
    stopped=1
fi

rm -f "$PID_FILE"

if curl -s "$DEBUG_URL" > /dev/null 2>&1; then
    echo "✗ 仍检测到 9222 调试 Chrome，请手动检查"
    exit 1
fi

if [ "$stopped" -eq 1 ]; then
    echo "✓ 已关闭 9222 调试 Chrome"
else
    echo "✓ 未检测到运行中的 9222 调试 Chrome"
fi
