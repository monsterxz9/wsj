#!/bin/bash
# 启动带有远程调试端口的 Chrome（后台模式）
# 使用独立的用户配置目录，不干扰日常使用的 Chrome

CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# 使用独立的 profile 目录
USER_DATA_DIR="$HOME/.wsj_chrome_profile"

# 检查 Chrome 是否已经在调试模式运行
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "✓ Chrome 已在调试模式运行 (端口 9222)"
    exit 0
fi

# 确保 profile 目录存在
mkdir -p "$USER_DATA_DIR"

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
    &

# 等待 Chrome 启动
sleep 3

if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "✓ Chrome 已在后台启动 (窗口隐藏在屏幕外)"
    echo ""
    echo "Profile 目录: $USER_DATA_DIR"
    echo ""
    echo "首次使用需要安装 Bypass Paywalls Clean 扩展："
    echo "  1. 临时移动窗口到可见区域"
    echo "  2. 安装扩展"
    echo "  3. 重新运行此脚本"
    echo ""
    echo "运行 scraper: python run_scraper.py"
else
    echo "✗ Chrome 启动失败"
    exit 1
fi
