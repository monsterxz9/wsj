"""
AI 翻译和词汇提取模块
使用 Google Gemini API（JSON 模式）
优化：批量翻译多篇文章，一次 API 调用处理所有文章
"""
import json
import re
import os
import asyncio
import hashlib
from typing import Optional
from dataclasses import dataclass
import httpx

from .scraper import Article


from .config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    TRANSLATION_CHUNK_SIZE,
    API_RETRY_ATTEMPTS,
    API_RETRY_DELAY
)
from .utils import setup_logging


@dataclass
class TranslatedArticle:
    """翻译后的文章"""
    title: str
    title_cn: str
    subhead: str
    subhead_cn: str
    byline: str
    byline_cn: str
    paragraphs: list[dict]  # [{"en": "...", "cn": "..."}, ...]
    vocabulary: list[dict]
    original_url: str
    date: str

    @property
    def id(self) -> str:
        return hashlib.md5(self.original_url.encode()).hexdigest()[:12]


# 批量翻译提示词
BATCH_TRANSLATION_PROMPT = '''你是一个专业的英中翻译专家。请将以下 {article_count} 篇英文新闻文章翻译成中文，并为每篇文章提取10个托业(TOEIC)考试词汇。

{articles_content}

## 输出要求
返回一个JSON对象，包含一个 "articles" 数组，数组中每个元素对应一篇文章的翻译结果。
每篇文章的结构如下：
- article_id: 文章编号（从1开始）
- title_cn: 标题的中文翻译
- subhead_cn: 副标题的中文翻译（如果没有副标题则为空字符串）
- byline_cn: 作者信息的中文翻译（如果没有则为空字符串）
- paragraphs_cn: 数组，包含每个段落的中文翻译，顺序与原文一致
- vocabulary: 数组，包含10个词汇对象，每个对象有以下字段：
  - word: 英文单词或短语
  - phonetic: 音标
  - meaning_en: 英文释义
  - meaning_cn: 中文释义
  - example: 文章中的例句
  - example_cn: 例句的中文翻译

注意：
1. 每篇文章的 paragraphs_cn 元素数量必须与原文段落数量一致
2. 每篇文章的 vocabulary 必须有 10 个词汇
3. 翻译要专业准确，符合新闻报道风格
4. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本
5. 确保 article_id 与输入的文章编号对应'''


# 单篇文章提示词（备用）
SINGLE_TRANSLATION_PROMPT = '''将以下英文新闻文章翻译成中文，并提取10个托业(TOEIC)考试词汇。

## 文章标题
{title}

## 文章副标题
{subhead}

## 作者信息
{byline}

## 正文段落
{paragraphs}

## 输出要求
返回一个JSON对象，包含以下字段：
- title_cn: 标题的中文翻译
- subhead_cn: 副标题的中文翻译（如果没有副标题则为空字符串）
- byline_cn: 作者信息的中文翻译（如果没有则为空字符串）
- paragraphs_cn: 数组，包含每个段落的中文翻译，顺序与原文一致，共{para_count}个段落
- vocabulary: 数组，包含10个词汇对象，每个对象有以下字段：
  - word: 英文单词或短语
  - phonetic: 音标
  - meaning_en: 英文释义
  - meaning_cn: 中文释义
  - example: 文章中的例句
  - example_cn: 例句的中文翻译

注意：
1. paragraphs_cn 必须有 {para_count} 个元素
2. vocabulary 必须有 10 个词汇
3. 翻译要专业准确，符合新闻报道风格
4. 特别注意：如果文章中出现 "Naval" (人名)，请翻译为 "纳瓦尔"，不要翻译成 "海军"
5. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本'''


class AITranslator:
    """AI 翻译器 - 使用 Gemini JSON 模式，支持批量翻译"""
    
    # 需要重试的网络异常
    RETRYABLE_EXCEPTIONS = (
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.NetworkError,
    )
    
    def __init__(self):
        self.logger = setup_logging("Translator")
        self.logger.info(f"Using Gemini: {GEMINI_MODEL}")
        self._client = httpx.AsyncClient(timeout=300)

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()

    async def _call_gemini(self, prompt: str, max_retries: int = API_RETRY_ATTEMPTS, max_output_tokens: int = 65536) -> dict:
        """调用 Google Gemini API - 使用 JSON 模式，带网络异常和 429 重试"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await self._client.post(
                    url,
                    params={"key": GEMINI_API_KEY},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": max_output_tokens,
                            "responseMimeType": "application/json",
                        },
                        "safetySettings": [
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    text = ""
                    try:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(text)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"JSON decode error: {e}")
                        return self._parse_json_fallback(text)
                    except (KeyError, IndexError) as e:
                        raise Exception(f"Gemini response error: {e}")
                
                elif response.status_code == 429:
                    retry_delay = 60
                    try:
                        error_data = response.json()
                        details = error_data.get("error", {}).get("details", [])
                        for detail in details:
                            if "retryDelay" in detail:
                                delay_str = detail["retryDelay"]
                                match = re.match(r"(\d+)s?", delay_str)
                                if match:
                                    retry_delay = int(match.group(1)) + 5
                                break
                    except (KeyError, ValueError, TypeError):
                        pass
                    
                    self.logger.warning(f"Rate limit (429). Waiting {retry_delay}s... (retry {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
                    continue
                
                else:
                    raise Exception(f"Gemini API error: {response.status_code} - {response.text}")
            
            except self.RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                # 指数退避: 2s, 4s, 8s...
                retry_delay = min(API_RETRY_DELAY * (2 ** attempt), 60)
                self.logger.warning(f"Network error: {type(e).__name__}. Waiting {retry_delay}s... (retry {attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                continue
        
        if last_exception:
            raise Exception(f"Gemini API failed after {max_retries} retries: {last_exception}")
        raise Exception(f"Gemini API failed after {max_retries} retries")
    
    def _parse_json_fallback(self, text: str) -> dict:
        """备用 JSON 解析"""
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'^```\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            json_str = match.group()
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
        
        return {"articles": []}
    
    def _format_article_for_prompt(self, article: Article, index: int) -> str:
        """格式化单篇文章用于批量提示词"""
        paragraphs_text = "\n".join([
            f"  [{i+1}] {p}" for i, p in enumerate(article.paragraphs)
        ])
        
        return f"""
=== 文章 {index} ===
标题: {article.title}
副标题: {article.subhead or "(无)"}
作者: {article.byline or "(无)"}
段落数: {len(article.paragraphs)}

正文:
{paragraphs_text}
"""
    
    async def translate_batch(self, articles: list[Article]) -> list[TranslatedArticle]:
        """
        批量翻译多篇文章 - 一次 API 调用处理所有文章
        """
        if not articles:
            return []
        
        self.logger.info(f"Batch translating {len(articles)} articles in ONE API call...")
        
        # 构建批量提示词
        articles_content = "\n".join([
            self._format_article_for_prompt(article, i + 1)
            for i, article in enumerate(articles)
        ])
        
        prompt = BATCH_TRANSLATION_PROMPT.format(
            article_count=len(articles),
            articles_content=articles_content,
        )
        
        # 估算需要的输出 token 数
        # 每篇文章大约需要 4000-5000 输出 token（翻译 + 词汇）
        estimated_tokens = len(articles) * 5000
        max_output_tokens = min(max(estimated_tokens, 20000), 100000)  # Gemini 2.5 Flash 支持更大输出
        
        self.logger.info(f"Estimated output tokens: {max_output_tokens}")
        
        # 调用 API
        result = await self._call_gemini(prompt, max_output_tokens=max_output_tokens)
        
        # 解析结果
        translated_articles = []
        articles_data = result.get("articles", [])
        
        for i, article in enumerate(articles):
            # 找到对应的翻译结果
            article_result = None
            for data in articles_data:
                if data.get("article_id") == i + 1:
                    article_result = data
                    break
            
            # 如果按 article_id 找不到，按顺序取
            if article_result is None and i < len(articles_data):
                article_result = articles_data[i]
            
            if article_result is None:
                self.logger.warning(f"Warning: No translation found for article {i + 1}: {article.title[:30]}...")
                continue
            
            # 组合双语段落
            paragraphs_cn = article_result.get("paragraphs_cn", [])
            paragraphs = []
            for j, en in enumerate(article.paragraphs):
                cn = paragraphs_cn[j] if j < len(paragraphs_cn) else ""
                paragraphs.append({"en": en, "cn": cn})
            
            vocab_count = len(article_result.get('vocabulary', []))
            para_translated = sum(1 for p in paragraphs if p.get("cn"))
            self.logger.info(f"Article {i + 1}: {para_translated}/{len(paragraphs)} paragraphs, {vocab_count} vocab")
            
            translated_articles.append(TranslatedArticle(
                title=article.title,
                title_cn=article_result.get("title_cn", ""),
                subhead=article.subhead,
                subhead_cn=article_result.get("subhead_cn", ""),
                byline=article.byline,
                byline_cn=article_result.get("byline_cn", ""),
                paragraphs=paragraphs,
                vocabulary=article_result.get("vocabulary", []),
                original_url=article.url,
                date=article.date,
            ))
        
        self.logger.info(f"Batch complete: {len(translated_articles)}/{len(articles)} articles translated")
        return translated_articles
    
    async def translate_article(self, article: Article) -> TranslatedArticle:
        """
        翻译单篇文章（备用方法）
        """
        self.logger.info(f"Translating single article: {article.title[:50]}...")
        
        paragraphs_text = "\n\n".join([
            f"[段落{i+1}] {p}" for i, p in enumerate(article.paragraphs)
        ])
        
        prompt = SINGLE_TRANSLATION_PROMPT.format(
            title=article.title,
            subhead=article.subhead or "(无)",
            byline=article.byline or "(无)",
            paragraphs=paragraphs_text,
            para_count=len(article.paragraphs),
        )
        
        result = await self._call_gemini(prompt)
        
        paragraphs_cn = result.get("paragraphs_cn", [])
        paragraphs = []
        for i, en in enumerate(article.paragraphs):
            cn = paragraphs_cn[i] if i < len(paragraphs_cn) else ""
            paragraphs.append({"en": en, "cn": cn})
        
        vocab_count = len(result.get('vocabulary', []))
        self.logger.info(f"Done: {len(paragraphs)} paragraphs, {vocab_count} vocab items")
        
        return TranslatedArticle(
            title=article.title,
            title_cn=result.get("title_cn", ""),
            subhead=article.subhead,
            subhead_cn=result.get("subhead_cn", ""),
            byline=article.byline,
            byline_cn=result.get("byline_cn", ""),
            paragraphs=paragraphs,
            vocabulary=result.get("vocabulary", []),
            original_url=article.url,
            date=article.date,
        )


async def translate_articles(articles: list[Article]) -> list[TranslatedArticle]:
    """
    批量翻译文章 - 使用分块处理避免 API 输出过大
    """
    logger = setup_logging("TranslatorRunner")
    
    if not GEMINI_API_KEY:
        logger.error("Error: No GEMINI_API_KEY configured!")
        logger.error("  Set GEMINI_API_KEY in .env file")
        return []
    
    if not articles:
        return []
    
    translator = AITranslator()

    try:
        # 将文章分块，确保响应不会因长度被截断
        chunk_size = TRANSLATION_CHUNK_SIZE
        all_translated = []

        for i in range(0, len(articles), chunk_size):
            chunk = articles[i:i + chunk_size]
            logger.info(f"Processing chunk {i//chunk_size + 1}/{(len(articles)-1)//chunk_size + 1} ({len(chunk)} articles)")
            try:
                translated_chunk = await translator.translate_batch(chunk)
                all_translated.extend(translated_chunk)
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                # 如果批量失败，尝试逐篇翻译
                logger.info("Falling back to single article translation...")
                for article in chunk:
                    try:
                        translated = await translator.translate_article(article)
                        all_translated.append(translated)
                    except Exception as ex:
                        logger.error(f"Failed to translate article {article.title}: {ex}")

        return all_translated
    finally:
        await translator.close()
