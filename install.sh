#!/bin/bash
# WSJ Scraper 安装脚本

set -e

echo "================================"
echo "WSJ Scraper 安装"
echo "================================"

cd "$(dirname "$0")"

# 1. 激活虚拟环境
echo "[1/4] 激活虚拟环境..."
source venv/bin/activate

# 2. 安装 Python 依赖
echo "[2/4] 安装 Python 依赖..."
pip install -r requirements.txt

# 3. 安装 CLI 命令
echo "[3/4] 安装 CLI 命令..."
pip install -e .

# 4. 安装 Playwright 浏览器
echo "[4/4] 安装 Playwright Chromium..."
playwright install chromium

echo ""
echo "================================"
echo "安装完成!"
echo "================================"
echo ""
echo "使用方法:"
echo "  # 手动运行（抓取首页文章）"
echo "  python run_scraper.py"
echo "  wsj-scraper"
echo ""
echo "  # 抓取指定文章"
echo "  python run_scraper.py --url 'https://www.wsj.com/articles/...'"
echo "  wsj-scraper --url 'https://www.wsj.com/articles/...'"
echo ""
echo "  # 显示浏览器窗口（调试）"
echo "  python run_scraper.py --no-headless"
echo "  wsj-scraper --no-headless"
echo ""
echo "  # 快速模式（跳过词汇提取）"
echo "  wsj-scraper --no-vocab"
echo ""
echo "  # 安装定时任务（每小时自动运行）"
echo "  ./scheduler.sh install"
echo ""
