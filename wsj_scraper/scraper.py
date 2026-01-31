"""
WSJ Article Scraper - Chrome Remote Debug 版本
连接到已打开的 Chrome 浏览器，使用现有的 cookies 和扩展
"""
import asyncio
import json
import re
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import hashlib

from playwright.async_api import async_playwright

from .config import (
    WSJ_HOME_URL,
    MAX_ARTICLES_PER_RUN,
    PAGE_LOAD_WAIT,
    REQUEST_TIMEOUT,
    HISTORY_FILE,
    PROJECT_ROOT,
)


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
    
    使用方式：
    1. 先用以下命令启动 Chrome（开启远程调试端口）：
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222
    
    2. 在 Chrome 中确保已安装 Bypass Paywalls Clean 扩展
    
    3. 运行脚本，它会连接到你的 Chrome 浏览器
    """
    
    CHROME_DEBUG_URL = "http://localhost:9222"
    
    def __init__(self, headless: bool = True):
        self.headless = headless  # 此模式下忽略
        self.browser = None
        self._playwright = None
        self._processed_urls = self._load_history()
    
    def _load_history(self) -> set:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return set(json.load(f).get('urls', []))
            except Exception:
                pass
        return set()
    
    def _save_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump({'urls': list(self._processed_urls)}, f)
    
    def _mark_processed(self, url: str):
        self._processed_urls.add(url)
        self._save_history()
    
    def is_processed(self, url: str) -> bool:
        return url in self._processed_urls
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def start(self):
        """连接到已运行的 Chrome 浏览器"""
        self._playwright = await async_playwright().start()
        
        try:
            self.browser = await self._playwright.chromium.connect_over_cdp(
                self.CHROME_DEBUG_URL,
                timeout=REQUEST_TIMEOUT * 1000,
            )
            print(f"[Scraper] Connected to Chrome at {self.CHROME_DEBUG_URL}")
            
            # 获取现有的 contexts
            contexts = self.browser.contexts
            print(f"[Scraper] Found {len(contexts)} browser contexts")
            
        except Exception as e:
            print(f"[Scraper] Failed to connect to Chrome: {e}")
            print("\n请先用以下命令启动 Chrome：")
            print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222\n')
            raise
    
    async def close(self):
        """断开连接（不关闭浏览器）"""
        # 不关闭浏览器，只是断开连接
        if self._playwright:
            await self._playwright.stop()
        print("[Scraper] Disconnected from Chrome")
    
    async def get_homepage_articles(self, limit: int = MAX_ARTICLES_PER_RUN) -> list[str]:
        """从 WSJ 首页获取文章链接"""
        # 使用现有的 context
        context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        page = await context.new_page()
        
        # 最小化窗口，防止抢焦点
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setWindowBounds", {
                "windowId": 1,
                "bounds": {"windowState": "minimized"}
            })
        except:
            pass
        
        articles = []
        
        try:
            print(f"[Scraper] Fetching WSJ homepage...")
            await page.goto(WSJ_HOME_URL, wait_until='domcontentloaded')
            
            # 等待页面加载
            await asyncio.sleep(PAGE_LOAD_WAIT + 3)
            
            # 获取所有链接
            links = await page.query_selector_all('a[href]')
            print(f"[Scraper] Found {len(links)} total links on page")
            
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
                        import re
                        if re.search(r'/[a-z-]+-[a-f0-9]{8}(\?|$)', href):
                            # 清理 URL
                            clean_url = href.split('?')[0]
                            
                            if clean_url not in seen_urls and not self.is_processed(clean_url):
                                seen_urls.add(clean_url)
                                articles.append(clean_url)
                                if len(articles) >= limit:
                                    break
                except:
                    continue
            
            print(f"[Scraper] Found {len(articles)} new articles")
            
        except Exception as e:
            print(f"[Scraper] Error fetching homepage: {e}")
        finally:
            await page.close()
        
        return articles[:limit]
    
    async def scrape_article(self, url: str) -> Optional[Article]:
        """抓取单篇文章内容"""
        context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        page = await context.new_page()
        
        # 最小化窗口，防止抢焦点
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Browser.setWindowBounds", {
                "windowId": 1,
                "bounds": {"windowState": "minimized"}
            })
        except:
            pass
        
        try:
            print(f"[Scraper] Fetching article: {url}")
            await page.goto(url, wait_until='domcontentloaded')
            
            # 等待内容加载（给 Bypass Paywalls Clean 时间处理）
            await asyncio.sleep(PAGE_LOAD_WAIT + 2)
            
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
                    if text and len(text) > 20 and not self._is_noise(text):
                        paragraphs.append(text)
                if paragraphs:
                    break
            
            if not title or not paragraphs:
                print(f"[Scraper] Failed to extract content")
                await page.screenshot(path=str(PROJECT_ROOT / "logs" / f"error_{datetime.now().strftime('%H%M%S')}.png"))
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
            
            print(f"[Scraper] Success: {title[:50]}...")
            return article
            
        except Exception as e:
            print(f"[Scraper] Error: {e}")
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
