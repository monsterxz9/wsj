#!/usr/bin/env python3
"""
WSJ Scraper 主入口
自动抓取 WSJ 文章，翻译并生成 PDF
"""
import asyncio
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from wsj_scraper.scraper import scrape_wsj_articles, WSJScraper
from wsj_scraper.translator import translate_articles
from wsj_scraper.pdf_generator import generate_pdf, save_json
from wsj_scraper.config import OUTPUT_DIR, MAX_ARTICLES_PER_RUN
from wsj_scraper.utils import setup_logging

logger = setup_logging("Main")

async def run_scraper(
    headless: bool = True,
    limit: int = MAX_ARTICLES_PER_RUN,
    save_json_file: bool = True,
    url: str = None,
):
    """
    运行完整的抓取-翻译-生成流程
    """
    logger.info(f"{'='*30} Start {'='*30}")
    
    # 1. 抓取文章
    logger.info("[Step 1/3] Scraping articles...")
    
    if url:
        # 抓取指定 URL
        async with WSJScraper(headless=headless) as scraper:
            article = await scraper.scrape_article(url)
            articles = [article] if article else []
    else:
        # 抓取首页文章
        articles = await scrape_wsj_articles(headless=headless, limit=limit)
    
    if not articles:
        logger.info("No new articles to process")
        return []
    
    logger.info(f"Scraped {len(articles)} articles")
    
    # 2. 翻译文章
    logger.info("[Step 2/3] Translating articles...")
    translated = await translate_articles(articles)
    
    if not translated:
        logger.error("Translation failed")
        return []
    
    logger.info(f"Translated {len(translated)} articles")
    
    # 3. 生成 PDF
    logger.info("[Step 3/3] Generating PDFs...")
    output_files = []
    
    for article in translated:
        try:
            pdf_path = generate_pdf(article)
            output_files.append(pdf_path)
            
            if save_json_file:
                save_json(article)
        except Exception as e:
            logger.error(f"Failed to generate PDF: {e}")
    
    # 完成
    logger.info(f"Completed! Generated {len(output_files)} PDFs")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"{'='*30} End {'='*30}")
    
    return output_files


def main():
    parser = argparse.ArgumentParser(
        description="WSJ Article Scraper - 自动抓取华尔街日报文章并生成 TOEIC 学习 PDF"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        help="抓取指定文章 URL（而不是首页）"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=MAX_ARTICLES_PER_RUN,
        help=f"最大抓取文章数（默认 {MAX_ARTICLES_PER_RUN}）"
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="显示浏览器窗口（调试用）"
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="不保存 JSON 文件"
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_scraper(
        headless=not args.no_headless,
        limit=args.limit,
        save_json_file=not args.no_json,
        url=args.url,
    ))


if __name__ == "__main__":
    main()
