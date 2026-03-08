#!/usr/bin/env python3
"""
WSJ Scraper 主入口
自动抓取 WSJ 文章，翻译并生成 PDF
"""

import asyncio
import argparse
import sys
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from wsj_scraper.scraper import scrape_wsj_articles, WSJScraper, Article
from wsj_scraper.translator import translate_articles
from wsj_scraper.pdf_generator import generate_pdf, save_json
from wsj_scraper.config import OUTPUT_DIR, MAX_ARTICLES_PER_RUN, RAW_DIR
from wsj_scraper.utils import setup_logging
import json

logger = setup_logging("Main")

CHROME_DEBUG_URL = "http://localhost:9222/json/version"
CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_USER_DATA_DIR = Path.home() / ".wsj_chrome_profile"
CHROME_PID_FILE = CHROME_USER_DATA_DIR / "chrome-debug-9222.pid"


def _is_debug_chrome_running() -> bool:
    """检查 9222 调试端口是否可用"""
    try:
        with urllib.request.urlopen(CHROME_DEBUG_URL, timeout=1):
            return True
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _is_pid_running(pid: int) -> bool:
    """检查进程是否仍在运行"""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def start_debug_chrome(wait_timeout: int = 20) -> bool:
    """启动 9222 调试端口的 Chrome"""
    if _is_debug_chrome_running():
        logger.info("Debug Chrome already running on port 9222")
        return True

    if not CHROME_PATH.exists():
        logger.error(f"Chrome executable not found: {CHROME_PATH}")
        return False

    CHROME_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 清理失效 PID 文件
    if CHROME_PID_FILE.exists():
        try:
            stale_pid = int(CHROME_PID_FILE.read_text(encoding="utf-8").strip())
            if not _is_pid_running(stale_pid):
                CHROME_PID_FILE.unlink(missing_ok=True)
        except (ValueError, OSError):
            CHROME_PID_FILE.unlink(missing_ok=True)

    logger.info("Starting debug Chrome on port 9222...")

    try:
        process = subprocess.Popen(
            [
                str(CHROME_PATH),
                "--remote-debugging-port=9222",
                "--window-position=-2000,-2000",
                "--window-size=800,600",
                "--no-first-run",
                f"--user-data-dir={CHROME_USER_DATA_DIR}",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        CHROME_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to launch debug Chrome: {e}")
        return False

    deadline = time.time() + max(1, wait_timeout)
    while time.time() < deadline:
        if _is_debug_chrome_running():
            logger.info("Debug Chrome started")
            return True
        time.sleep(0.5)

    logger.error("Timed out waiting for debug Chrome to start")
    return False


def shutdown_debug_chrome() -> bool:
    """关闭 9222 调试端口的 Chrome，避免后台进程累积"""
    pids = set()

    # 1) 优先读取 PID 文件
    if CHROME_PID_FILE.exists():
        try:
            pid = int(CHROME_PID_FILE.read_text(encoding="utf-8").strip())
            if pid > 0:
                pids.add(pid)
        except (ValueError, OSError):
            pass

    # 2) 兜底：扫描命令行参数匹配的调试 Chrome 进程
    pattern = f"--remote-debugging-port=9222.*--user-data-dir={CHROME_USER_DATA_DIR}"
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
    except Exception as e:
        logger.warning(f"Failed to scan Chrome process list: {e}")

    if not pids:
        try:
            CHROME_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        logger.info("No debug Chrome process to stop")
        return False

    # 先温和终止，再强制终止
    remaining = sorted(pids)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in remaining:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                continue
            except PermissionError:
                logger.warning(f"No permission to stop process {pid}")

        if sig == signal.SIGTERM:
            time.sleep(1)

        remaining = [pid for pid in remaining if _is_pid_running(pid)]
        if not remaining:
            break

    try:
        CHROME_PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    if remaining:
        logger.warning(f"Some debug Chrome processes are still running: {remaining}")
        return False

    logger.info(f"Stopped debug Chrome process(es): {sorted(pids)}")
    return True


def load_raw_articles() -> list[Article]:
    """加载缓存的未翻译文章"""
    articles = []
    if not RAW_DIR.exists():
        return []

    for file_path in RAW_DIR.glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                articles.append(Article(**data))
        except Exception as e:
            logger.warning(f"Failed to load raw article {file_path}: {e}")

    return articles


def clean_raw_article(article_id: str):
    """删除已处理的原始文章缓存"""
    try:
        file_path = RAW_DIR / f"{article_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Removed processed raw article: {article_id}")
    except Exception as e:
        logger.warning(f"Failed to delete raw article {article_id}: {e}")


async def run_scraper(
    headless: bool = True,
    limit: int = MAX_ARTICLES_PER_RUN,
    save_json_file: bool = True,
    url: Optional[str] = None,
    shutdown_chrome_after_run: bool = True,
    auto_start_chrome: bool = True,
):
    """
    运行完整的抓取-翻译-生成流程
    """
    logger.info(f"{'=' * 30} Start {'=' * 30}")
    output_files = []

    try:
        if auto_start_chrome:
            if not start_debug_chrome():
                logger.error("Unable to start debug Chrome")
                return []
        elif not _is_debug_chrome_running():
            logger.error("Debug Chrome is not running on port 9222")
            logger.error(
                "Run `wsj-scraper --start-chrome` first or remove --no-auto-start-chrome"
            )
            return []

        articles = []

        # 0. 加载未翻译的缓存文章 (仅在非指定URL模式下)
        if not url:
            cached_articles = load_raw_articles()
            if cached_articles:
                logger.info(
                    f"Loaded {len(cached_articles)} cached articles to retry translation"
                )
                articles.extend(cached_articles)

        # 1. 抓取文章
        logger.info("[Step 1/3] Scraping articles...")

        if url:
            # 抓取指定 URL
            async with WSJScraper(headless=headless) as scraper:
                article = await scraper.scrape_article(url)
                if article:
                    articles.append(article)
        else:
            # 抓取首页文章
            # 检查是否还需要抓取更多
            # 如果缓存已经很多了，也许可以减少抓取数量？
            # 这里暂时保持原逻辑，继续抓取新文章
            new_articles = await scrape_wsj_articles(headless=headless, limit=limit)
            articles.extend(new_articles)

        # 去重 (以防万一)
        unique_articles = {a.id: a for a in articles}
        articles = list(unique_articles.values())

        if not articles:
            logger.info("No articles to process")
            return []

        logger.info(f"Total articles to process: {len(articles)}")

        # 2. 翻译文章
        logger.info("[Step 2/3] Translating articles...")
        translated = await translate_articles(articles)

        if not translated:
            logger.error("Translation failed")
            return []

        logger.info(f"Translated {len(translated)} articles")

        # 3. 生成 PDF
        logger.info("[Step 3/3] Generating PDFs...")

        for article in translated:
            try:
                pdf_path = generate_pdf(article)
                output_files.append(pdf_path)

                if save_json_file:
                    save_json(article)

                # 清理原始缓存
                clean_raw_article(article.id)

            except Exception as e:
                logger.error(f"Failed to generate PDF: {e}")

        # 完成
        logger.info(f"Completed! Generated {len(output_files)} PDFs")
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info(f"{'=' * 30} End {'=' * 30}")

        return output_files
    finally:
        if shutdown_chrome_after_run:
            shutdown_debug_chrome()


def main():
    parser = argparse.ArgumentParser(
        description="WSJ Article Scraper - 自动抓取华尔街日报文章并生成 TOEIC 学习 PDF"
    )
    parser.add_argument("--url", "-u", type=str, help="抓取指定文章 URL（而不是首页）")
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=MAX_ARTICLES_PER_RUN,
        help=f"最大抓取文章数（默认 {MAX_ARTICLES_PER_RUN}）",
    )
    parser.add_argument(
        "--no-headless", action="store_true", help="显示浏览器窗口（调试用）"
    )
    parser.add_argument("--no-json", action="store_true", help="不保存 JSON 文件")
    parser.add_argument(
        "--keep-chrome",
        action="store_true",
        help="爬取完成后不关闭 9222 调试 Chrome（默认会自动关闭）",
    )
    parser.add_argument(
        "--start-chrome",
        action="store_true",
        help="仅启动 9222 调试 Chrome 并退出",
    )
    parser.add_argument(
        "--stop-chrome",
        action="store_true",
        help="仅关闭 9222 调试 Chrome 并退出",
    )
    parser.add_argument(
        "--no-auto-start-chrome",
        action="store_true",
        help="不自动启动 9222 调试 Chrome（默认自动启动）",
    )

    args = parser.parse_args()

    if args.start_chrome and args.stop_chrome:
        parser.error("--start-chrome and --stop-chrome cannot be used together")

    if args.start_chrome:
        raise SystemExit(0 if start_debug_chrome() else 1)

    if args.stop_chrome:
        shutdown_debug_chrome()
        raise SystemExit(0)

    asyncio.run(
        run_scraper(
            headless=not args.no_headless,
            limit=args.limit,
            save_json_file=not args.no_json,
            url=args.url,
            shutdown_chrome_after_run=not args.keep_chrome,
            auto_start_chrome=not args.no_auto_start_chrome,
        )
    )


if __name__ == "__main__":
    main()
