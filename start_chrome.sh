#!/bin/bash
# 启动带有远程调试端口的 Chrome（后台模式）
# 使用独立的用户配置目录，不干扰日常使用的 Chrome

set -euo pipefail

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# 使用独立的 profile 目录
USER_DATA_DIR="$HOME/.wsj_chrome_profile"
PID_FILE="$USER_DATA_DIR/chrome-debug-9222.pid"
DEBUG_URL="http://localhost:9222/json/version"

if [ ! -x "$CHROME_PATH" ]; then
    echo "✗ 未找到 Chrome 可执行文件: $CHROME_PATH"
    exit 1
fi

# 确保 profile 目录存在
mkdir -p "$USER_DATA_DIR"

# 如果 PID 文件存在但进程已不存在，清理 PID 文件
if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && ! kill -0 "$pid" >/dev/null 2>&1; then
        rm -f "$PID_FILE"
    fi
fi

# 检查 Chrome 是否已经在调试模式运行
if curl -s "$DEBUG_URL" > /dev/null 2>&1; then
    echo "✓ Chrome 已在调试模式运行 (端口 9222)"
    exit 0
fi

echo "启动 Chrome (后台模式, 调试端口 9222)..."

# 启动 Chrome（窗口在屏幕外，不会干扰工作）：
# --window-position: 把窗口放到屏幕外
# --window-size: 小窗口
# --no-first-run: 跳过首次运行提示
# --user-data-dir: 使用独立的配置目录
"$CHROME_PATH" \
    --remote-debugging-port=9222 \
    --window-position=-2000,-2000 \
    --window-size=800,600 \
    --no-first-run \
    --user-data-dir="$USER_DATA_DIR" \
    --no-default-browser-check \
    &

CHROME_PID=$!
echo "$CHROME_PID" > "$PID_FILE"

# 等待 Chrome 启动
sleep 3

if curl -s "$DEBUG_URL" > /dev/null 2>&1; then
    echo "✓ Chrome 已在后台启动 (窗口隐藏在屏幕外)"
    echo ""
    echo "Profile 目录: $USER_DATA_DIR"
    echo "PID 文件: $PID_FILE"
    echo ""
    echo "首次使用需要安装 Bypass Paywalls Clean 扩展："
    echo "  1. 临时移动窗口到可见区域"
    echo "  2. 安装扩展"
    echo "  3. 重新运行此脚本"
    echo ""
    echo "运行 scraper: python run_scraper.py"
    echo "停止调试 Chrome: ./stop_chrome.sh"
else
    rm -f "$PID_FILE"
    echo "✗ Chrome 启动失败"
    exit 1
fi
