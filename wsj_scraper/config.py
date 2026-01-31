"""
WSJ Scraper Configuration
配置文件 - 请根据你的实际情况修改
"""
import os
from pathlib import Path

# ==================== 路径配置 ====================
# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 输出目录 - 可以改成 iCloud Drive 路径
# macOS iCloud Drive 路径通常是:
# ~/Library/Mobile Documents/com~apple~CloudDocs/WSJ_Articles
# 或者: ~/Library/CloudStorage/iCloud Drive/WSJ_Articles
OUTPUT_DIR = PROJECT_ROOT / "output"

# Chrome 用户数据目录 (用于加载已安装的扩展)
CHROME_USER_DATA_DIR = Path.home() / "Library/Application Support/Google/Chrome"
CHROME_PROFILE = "Default"

# ==================== 抓取配置 ====================
# WSJ 首页URL
WSJ_HOME_URL = "https://www.wsj.com"

# 每次抓取的最大文章数
MAX_ARTICLES_PER_RUN = 5

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30

# 页面加载等待时间（秒）
PAGE_LOAD_WAIT = 5

# ==================== AI 翻译配置 ====================
# 使用 Ollama 本地模型 (免费) 或 OpenAI API
USE_OLLAMA = False  # 设为 False 使用 OpenAI
OLLAMA_MODEL = "qwen2.5:14b"  # 或者 "llama3.2" 等

# OpenAI 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"  # 便宜又好用

# ==================== PDF 配置 ====================
# 中文字体路径
CHINESE_FONT_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"
ARIAL_UNICODE_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

# ==================== 历史记录 ====================
# 已处理文章的记录文件
HISTORY_FILE = PROJECT_ROOT / "wsj_scraper" / ".processed_articles.json"
