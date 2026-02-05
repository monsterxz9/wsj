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


def load_raw_articles() -> list[Article]:
    """加载缓存的未翻译文章"""
    articles = []
    if not RAW_DIR.exists():
        return []
    
    for file_path in RAW_DIR.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
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
):
    """
    运行完整的抓取-翻译-生成流程
    """
    logger.info(f"{'='*30} Start {'='*30}")
    
    articles = []
    
    # 0. 加载未翻译的缓存文章 (仅在非指定URL模式下)
    if not url:
        cached_articles = load_raw_articles()
        if cached_articles:
            logger.info(f"Loaded {len(cached_articles)} cached articles to retry translation")
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
    output_files = []
    
    import hashlib
    
    for article in translated:
        try:
            pdf_path = generate_pdf(article)
            output_files.append(pdf_path)
            
            if save_json_file:
                save_json(article)
            
            # 清理原始缓存
            # 计算 ID
            art_id = hashlib.md5(article.original_url.encode()).hexdigest()[:12]
            clean_raw_article(art_id)
            
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
