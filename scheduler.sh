#!/bin/bash
# 安装/管理 launchd 定时任务

PLIST_NAME="com.user.wsj-scraper.plist"
PLIST_SRC="$(dirname "$0")/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"

case "$1" in
    install|start)
        echo "安装定时任务..."
        
        # 停止现有任务
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        
        # 复制 plist 文件
        cp "$PLIST_SRC" "$PLIST_DST"
        
        # 加载任务
        launchctl load "$PLIST_DST"
        
        echo "✓ 定时任务已安装"
        echo "  任务将每小时自动运行"
        echo "  日志位置: $(dirname "$0")/logs/"
        ;;
        
    stop|uninstall)
        echo "停止定时任务..."
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        echo "✓ 定时任务已停止"
        ;;
        
    status)
        if launchctl list | grep -q "wsj-scraper"; then
            echo "✓ 定时任务正在运行"
            launchctl list | grep wsj-scraper
        else
            echo "✗ 定时任务未运行"
        fi
        ;;
        
    run)
        echo "手动触发任务..."
        launchctl start "$PLIST_NAME"
        echo "✓ 任务已触发，查看日志: tail -f $(dirname "$0")/logs/scraper.log"
        ;;
        
    logs)
        tail -f "$(dirname "$0")/logs/scraper.log"
        ;;
        
    *)
        echo "用法: $0 {install|stop|status|run|logs}"
        echo ""
        echo "  install  - 安装并启动定时任务"
        echo "  stop     - 停止并卸载定时任务"
        echo "  status   - 查看任务状态"
        echo "  run      - 立即运行一次"
        echo "  logs     - 查看日志"
        exit 1
        ;;
esac
