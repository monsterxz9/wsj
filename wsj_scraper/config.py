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
REQUEST_TIMEOUT = 60

# 页面加载等待时间（秒）
PAGE_LOAD_WAIT = 15

# ==================== 日志配置 ====================
LOG_DIR = PROJECT_ROOT / "logs"
LOG_LEVEL = "INFO"

# ==================== AI 翻译配置 ====================
# Google Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"

# 批量翻译配置
TRANSLATION_CHUNK_SIZE = 1  # 每次API调用处理的文章数 (Gemini 2.0 Flash context window很大，可以调大)
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 2  # 秒

# ==================== 抓取行为配置 ====================
# 页面滚动等待时间（秒）- 让内容完全加载
SCROLL_WAIT_TIME = 2

# 文章内容最小长度（字符）- 过滤掉空文章
MIN_ARTICLE_LENGTH = 20

# ==================== PDF 生成配置 ====================
# 段落长度阈值（字符）- 超过此长度会拆分成多列
PARAGRAPH_SPLIT_THRESHOLD = 2000

# ==================== PDF 配置 ====================
# 中文字体路径
CHINESE_FONT_PATH = "/System/Library/Fonts/Supplemental/Songti.ttc"
ARIAL_UNICODE_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

# ==================== 历史记录 ====================
# 已处理文章的记录文件
HISTORY_FILE = PROJECT_ROOT / "wsj_scraper" / ".processed_articles.json"

# 未翻译文章的缓存目录
RAW_DIR = PROJECT_ROOT / "wsj_scraper" / ".raw_cache"
