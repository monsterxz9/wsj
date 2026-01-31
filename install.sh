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

# 3. 安装 Playwright 浏览器
echo "[3/4] 安装 Playwright Chromium..."
playwright install chromium

# 4. 检查 Ollama（可选）
echo "[4/4] 检查 Ollama..."
if command -v ollama &> /dev/null; then
    echo "✓ Ollama 已安装"
    if ollama list | grep -q "qwen2.5"; then
        echo "✓ qwen2.5 模型已下载"
    else
        echo "⚠ 建议下载翻译模型: ollama pull qwen2.5:14b"
    fi
else
    echo "⚠ Ollama 未安装"
    echo "  如需使用本地翻译，请安装 Ollama: https://ollama.ai"
    echo "  或者配置 OPENAI_API_KEY 使用 OpenAI API"
fi

echo ""
echo "================================"
echo "安装完成!"
echo "================================"
echo ""
echo "使用方法:"
echo "  # 手动运行（抓取首页文章）"
echo "  python run_scraper.py"
echo ""
echo "  # 抓取指定文章"
echo "  python run_scraper.py --url 'https://www.wsj.com/articles/...'"
echo ""
echo "  # 显示浏览器窗口（调试）"
echo "  python run_scraper.py --no-headless"
echo ""
echo "  # 安装定时任务（每小时自动运行）"
echo "  ./install_scheduler.sh"
echo ""
