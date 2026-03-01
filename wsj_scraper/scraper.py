"""
WSJ Article Scraper - Chrome Remote Debug 版本
连接到已打开的 Chrome 浏览器，使用现有的 cookies 和扩展
"""
import asyncio
import json
import logging
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import hashlib

from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async
except ImportError:
    # 兼容本地开发环境如果没有安装 stealth
    stealth_async = None

from .config import (
    WSJ_HOME_URL,
    MAX_ARTICLES_PER_RUN,
    PAGE_LOAD_WAIT,
    REQUEST_TIMEOUT,
    HISTORY_FILE,
    PROJECT_ROOT,
    SCROLL_WAIT_TIME,
    MIN_ARTICLE_LENGTH,
    LOG_DIR,
    RAW_DIR,
    MAX_HISTORY_SIZE,
)
from .utils import setup_logging, minimize_window


@dataclass
class Article:
    """文章数据结构"""
    url: str
    title: str
    subhead: str
    byline: str
    date: str
    paragraphs: list[str]
    scraped_at: str
    
    @property
    def id(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()[:12]
    
    def to_dict(self) -> dict:
        return asdict(self)


class WSJScraper:
    """
    WSJ 文章抓取器
    
    连接到已在运行的真实 Google Chrome 浏览器
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self._playwright = None
        self._processed_urls = self._load_history()
        self._history_dirty = False
        self.CHROME_DEBUG_URL = "http://localhost:9222"
        self.logger = setup_logging("Scraper")
    
    def _load_history(self) -> set:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return set(json.load(f).get('urls', []))
            except Exception as e:
                self.logger.warning(f"Failed to load history: {e}")
        return set()
    
    def _save_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        urls = list(self._processed_urls)
        # 超过上限时只保留最近的记录
        if len(urls) > MAX_HISTORY_SIZE:
            urls = urls[-MAX_HISTORY_SIZE:]
            self._processed_urls = set(urls)
        with open(HISTORY_FILE, 'w') as f:
            json.dump({'urls': urls}, f)
    
    def _mark_processed(self, url: str):
        self._processed_urls.add(url)
        self._history_dirty = True
    
    def is_processed(self, url: str) -> bool:
        return url in self._processed_urls
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """连接到已运行的 Chrome"""
        self._playwright = await async_playwright().start()
        
        try:
            # 连接到远程调试端口
            self.browser = await self._playwright.chromium.connect_over_cdp(
                self.CHROME_DEBUG_URL,
                timeout=REQUEST_TIMEOUT * 1000,
            )
            self.logger.info(f"Connected to real Chrome at {self.CHROME_DEBUG_URL}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Chrome: {e}")
            raise
    
    async def close(self):
        """断开连接，保存历史记录"""
        if self._history_dirty:
            self._save_history()
        if self._playwright:
            await self._playwright.stop()
        self.logger.info("Disconnected from Chrome")
    
    async def get_homepage_articles(self, limit: int = MAX_ARTICLES_PER_RUN) -> list[str]:
        """从 WSJ 首页获取文章链接"""
        if not self.browser:
            raise RuntimeError("Browser not connected")
            
        context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        page = await context.new_page()
        
        # 应用 Stealth
        if stealth_async:
            await stealth_async(page)

        # 最小化窗口
        await minimize_window(page)
        
        articles = []
        
        try:
            self.logger.info("Fetching WSJ homepage...")
            
            # 模拟随机等待
            await asyncio.sleep(random.uniform(1, 3))
            
            # 添加 Referer
            await page.set_extra_http_headers({
                "Referer": "https://www.google.com/",
                "Accept-Language": "en-US,en;q=0.9"
            })
            
            # 模拟人类滚动
            async def human_scroll():
                for _ in range(random.randint(2, 4)):
                    await page.mouse.wheel(0, random.randint(300, 600))
                    await asyncio.sleep(random.uniform(0.5, 1.5))

            await page.goto(WSJ_HOME_URL, wait_until='domcontentloaded')
            await human_scroll()
            
            # 等待页面进一步加载
            await asyncio.sleep(PAGE_LOAD_WAIT)
            
            # Debug: 打印标题和截图
            title = await page.title()
            self.logger.debug(f"Page Title: {title}")

            # Save debug screenshot only at DEBUG level
            if self.logger.isEnabledFor(logging.DEBUG):
                debug_shot = LOG_DIR / f"homepage_{datetime.now():%Y%m%d_%H%M%S}.png"
                await page.screenshot(path=str(debug_shot), full_page=True)
            
            # 获取所有链接
            links = await page.query_selector_all('a[href]')
            self.logger.info(f"Found {len(links)} total links on page")
            
            seen_urls = set()
            for link in links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    # WSJ 文章 URL 模式:
                    # - 包含类别 + 标题 + 短 ID，如 /us-news/law/title-abc123
                    # - 或旧格式 /articles/title
                    # 过滤掉导航链接（只有类别没有具体文章）
                    
                    if 'wsj.com/' in href or href.startswith('/'):
                        # 规范化 URL
                        if href.startswith('/'):
                            href = f"https://www.wsj.com{href}"
                        
                        # 检查是否是文章链接（包含8位十六进制ID结尾）
                        if re.search(r'/[a-z-]+-[a-f0-9]{8}(\?|$)', href):
                            # 清理 URL
                            clean_url = href.split('?')[0]
                            
                            if clean_url not in seen_urls and not self.is_processed(clean_url):
                                seen_urls.add(clean_url)
                                articles.append(clean_url)
                                if len(articles) >= limit:
                                    break
                except Exception:
                    continue
            
            self.logger.info(f"Found {len(articles)} new articles")
            
        except Exception as e:
            self.logger.error(f"Error fetching homepage: {e}")
        finally:
            await page.close()
        
        return articles[:limit]
    
    async def scrape_article(self, url: str) -> Optional[Article]:
        """抓取单篇文章内容"""
        if not self.browser:
            raise RuntimeError("Browser not connected")

        context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        page = await context.new_page()
        
        # 应用 Stealth
        if stealth_async:
            await stealth_async(page)
            
        # 最小化窗口
        await minimize_window(page)
        
        try:
            self.logger.info(f"Fetching article: {url}")
            await page.goto(url, wait_until='domcontentloaded')
            
            # 等待内容加载（给 Bypass Paywalls Clean 时间处理）
            await asyncio.sleep(PAGE_LOAD_WAIT)
            
            # 提取标题
            title = ""
            for sel in ['h1', 'article h1', '[data-testid="headline"]']:
                elem = await page.query_selector(sel)
                if elem:
                    title = (await elem.inner_text()).strip()
                    if title:
                        break
            
            # 提取副标题
            subhead = ""
            for sel in ['.sub-head', '[data-testid="article-subhead"]']:
                elem = await page.query_selector(sel)
                if elem:
                    subhead = (await elem.inner_text()).strip()
                    if subhead:
                        break
            
            # 提取作者
            byline = ""
            for sel in ['.byline', '[class*="byline"]']:
                elem = await page.query_selector(sel)
                if elem:
                    byline = (await elem.inner_text()).strip()
                    if byline:
                        break
            
            # 提取正文
            paragraphs = []
            for sel in ['article p', '.article-content p', '[data-type="paragraph"]']:
                elems = await page.query_selector_all(sel)
                for elem in elems:
                    text = (await elem.inner_text()).strip()
                    if text and len(text) > MIN_ARTICLE_LENGTH and not self._is_noise(text):
                        paragraphs.append(text)
                if paragraphs:
                    break
            
            if not title or not paragraphs:
                self.logger.warning(f"Failed to extract content for {url}")
                error_shot = LOG_DIR / f"error_{datetime.now():%H%M%S}.png"
                await page.screenshot(path=str(error_shot))
                return None
            
            self._mark_processed(url)
            
            article = Article(
                url=url,
                title=title,
                subhead=subhead,
                byline=byline,
                date=datetime.now().strftime("%Y-%m-%d"),
                paragraphs=paragraphs,
                scraped_at=datetime.now().isoformat(),
            )
            
            # Save raw article to cache
            try:
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                raw_path = RAW_DIR / f"{article.id}.json"
                with open(raw_path, 'w', encoding='utf-8') as f:
                    json.dump(article.to_dict(), f, ensure_ascii=False, indent=2)
                self.logger.debug(f"Saved raw article to {raw_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save raw article: {e}")
            
            self.logger.info(f"Success: {title[:50]}...")
            return article
            
        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {e}")
            return None
        finally:
            await page.close()
    
    def _is_noise(self, text: str) -> bool:
        noise = [
            r'^Subscribe', r'^Sign up', r'^Newsletter', r'^Advertisement',
            r'^Copyright', r'SHARE YOUR THOUGHTS', r'Join the conversation',
            r'^Read more', r'^\d+\s*min read', r'^Listen to article',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in noise)


async def scrape_wsj_articles(headless: bool = True, limit: int = MAX_ARTICLES_PER_RUN) -> list[Article]:
    """主入口函数"""
    articles = []
    async with WSJScraper(headless=headless) as scraper:
        urls = await scraper.get_homepage_articles(limit=limit)
        for url in urls:
            article = await scraper.scrape_article(url)
            if article:
                articles.append(article)
            await asyncio.sleep(random.uniform(2, 4))
    return articles
