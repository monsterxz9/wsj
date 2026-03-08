"""
AI 翻译和词汇提取模块
使用 Google Gemini API（JSON 模式）
"""

import json
import re
import asyncio
import hashlib
from dataclasses import dataclass
import httpx

from .scraper import Article


from .config import GEMINI_API_KEY, GEMINI_MODEL, API_RETRY_ATTEMPTS, API_RETRY_DELAY
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


# 批量翻译提示词（含词汇）
BATCH_TRANSLATION_PROMPT = """你是一个专业的英中翻译专家。请将以下 {article_count} 篇英文新闻文章翻译成中文，并为每篇文章提取{vocabulary_count}个托业(TOEIC)考试词汇。

{articles_content}

## 输出要求
返回一个JSON对象，包含一个 "articles" 数组，数组中每个元素对应一篇文章的翻译结果。
每篇文章的结构如下：
- article_id: 文章编号（从1开始）
- title_cn: 标题的中文翻译
- subhead_cn: 副标题的中文翻译（如果没有副标题则为空字符串）
- byline_cn: 作者信息的中文翻译（如果没有则为空字符串）
- paragraphs_cn: 数组，包含每个段落的中文翻译，顺序与原文一致
- vocabulary: 数组，包含{vocabulary_count}个词汇对象，每个对象有以下字段：
  - word: 英文单词或短语
  - phonetic: 音标
  - meaning_en: 英文释义
  - meaning_cn: 中文释义
  - example: 文章中的例句
  - example_cn: 例句的中文翻译

注意：
1. 每篇文章的 paragraphs_cn 元素数量必须与原文段落数量一致
2. 每篇文章的 vocabulary 必须有 {vocabulary_count} 个词汇
3. 翻译要专业准确，符合新闻报道风格
4. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本
5. 确保 article_id 与输入的文章编号对应"""


# 批量翻译提示词（无词汇，速度更快）
BATCH_TRANSLATION_PROMPT_NO_VOCAB = """你是一个专业的英中翻译专家。请将以下 {article_count} 篇英文新闻文章翻译成中文。

{articles_content}

## 输出要求
返回一个JSON对象，包含一个 "articles" 数组，数组中每个元素对应一篇文章的翻译结果。
每篇文章的结构如下：
- article_id: 文章编号（从1开始）
- title_cn: 标题的中文翻译
- subhead_cn: 副标题的中文翻译（如果没有副标题则为空字符串）
- byline_cn: 作者信息的中文翻译（如果没有则为空字符串）
- paragraphs_cn: 数组，包含每个段落的中文翻译，顺序与原文一致

注意：
1. 每篇文章的 paragraphs_cn 元素数量必须与原文段落数量一致
2. 翻译要专业准确，符合新闻报道风格
3. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本
4. 确保 article_id 与输入的文章编号对应"""


# 单篇文章提示词（含词汇）
SINGLE_TRANSLATION_PROMPT = """将以下英文新闻文章翻译成中文，并提取{vocabulary_count}个托业(TOEIC)考试词汇。

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
- vocabulary: 数组，包含{vocabulary_count}个词汇对象，每个对象有以下字段：
  - word: 英文单词或短语
  - phonetic: 音标
  - meaning_en: 英文释义
  - meaning_cn: 中文释义
  - example: 文章中的例句
  - example_cn: 例句的中文翻译

注意：
1. paragraphs_cn 必须有 {para_count} 个元素
2. vocabulary 必须有 {vocabulary_count} 个词汇
3. 翻译要专业准确，符合新闻报道风格
4. 特别注意：如果文章中出现 "Naval" (人名)，请翻译为 "纳瓦尔"，不要翻译成 "海军"
5. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本"""


# 单篇文章提示词（无词汇，速度更快）
SINGLE_TRANSLATION_PROMPT_NO_VOCAB = """将以下英文新闻文章翻译成中文。

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

注意：
1. paragraphs_cn 必须有 {para_count} 个元素
2. 翻译要专业准确，符合新闻报道风格
3. 特别注意：如果文章中出现 "Naval" (人名)，请翻译为 "纳瓦尔"，不要翻译成 "海军"
4. 不要在输出中使用任何 markdown 格式（如 **加粗** 或 *斜体*），保持纯文本"""


class AITranslator:
    """AI 翻译器 - 使用 Gemini JSON 模式"""

    # 需要重试的网络异常
    RETRYABLE_EXCEPTIONS = (
        httpx.RemoteProtocolError,
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.NetworkError,
    )

    FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash")

    @classmethod
    def _build_model_candidates(cls, preferred_model: str) -> list[str]:
        candidates: list[str] = []
        for model in (preferred_model, *cls.FALLBACK_MODELS):
            normalized = (model or "").strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    @staticmethod
    def _is_model_unavailable(response: httpx.Response) -> bool:
        if response.status_code != 404:
            return False

        message = ""
        try:
            message = response.json().get("error", {}).get("message", "")
        except Exception:
            message = response.text

        normalized = message.lower()
        return (
            "is not found for api version" in normalized
            or "is not supported for generatecontent" in normalized
            or "model" in normalized
            and "not found" in normalized
        )

    def __init__(self):
        self.logger = setup_logging("Translator")
        self._model_candidates = self._build_model_candidates(GEMINI_MODEL)
        self._active_model = self._model_candidates[0]
        self.logger.info(f"Using Gemini preferred model: {self._active_model}")
        self._client = httpx.AsyncClient(timeout=300)

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()

    async def _call_gemini(
        self,
        prompt: str,
        max_retries: int = API_RETRY_ATTEMPTS,
        max_output_tokens: int = 65536,
    ) -> dict:
        """调用 Google Gemini API - JSON 模式，带模型自动回退与重试"""
        model_order = [self._active_model] + [
            model for model in self._model_candidates if model != self._active_model
        ]
        unavailable_models: list[str] = []

        for model in model_order:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent"
            )
            last_exception = None
            model_unavailable = False

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
                                {
                                    "category": "HARM_CATEGORY_HARASSMENT",
                                    "threshold": "BLOCK_NONE",
                                },
                                {
                                    "category": "HARM_CATEGORY_HATE_SPEECH",
                                    "threshold": "BLOCK_NONE",
                                },
                                {
                                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                    "threshold": "BLOCK_NONE",
                                },
                                {
                                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                    "threshold": "BLOCK_NONE",
                                },
                            ],
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        text = ""
                        try:
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            result = json.loads(text)
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"JSON decode error: {e}")
                            result = self._parse_json_fallback(text)
                        except (KeyError, IndexError) as e:
                            raise Exception(f"Gemini response error: {e}")

                        if model != self._active_model:
                            self.logger.warning(
                                f"Gemini model fallback: {self._active_model} -> {model}"
                            )
                            self._active_model = model
                        return result

                    if self._is_model_unavailable(response):
                        model_unavailable = True
                        unavailable_models.append(model)
                        self.logger.warning(
                            f"Gemini model unavailable for generateContent: {model}"
                        )
                        break

                    if response.status_code == 429:
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

                        self.logger.warning(
                            f"Rate limit (429). Waiting {retry_delay}s... (retry {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_delay)
                        continue

                    raise Exception(
                        f"Gemini API error: {response.status_code} - {response.text}"
                    )

                except self.RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    retry_delay = min(API_RETRY_DELAY * (2**attempt), 60)
                    self.logger.warning(
                        f"Network error: {type(e).__name__}. Waiting {retry_delay}s... (retry {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)
                    continue

            if model_unavailable:
                continue

            if last_exception:
                raise Exception(
                    f"Gemini API failed after {max_retries} retries: {last_exception}"
                )
            raise Exception(f"Gemini API failed after {max_retries} retries")

        raise Exception(
            "No available Gemini model for generateContent. "
            f"Tried: {', '.join(model_order)}; unavailable: {', '.join(unavailable_models)}"
        )

    def _parse_json_fallback(self, text: str) -> dict:
        """备用 JSON 解析"""
        text = re.sub(r"^```json\s*", "", text.strip())
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            json_str = match.group()
            json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass

        return {"articles": []}

    def _format_article_for_prompt(self, article: Article, index: int) -> str:
        """格式化单篇文章用于批量提示词"""
        paragraphs_text = "\n".join(
            [f"  [{i + 1}] {p}" for i, p in enumerate(article.paragraphs)]
        )

        return f"""
=== 文章 {index} ===
标题: {article.title}
副标题: {article.subhead or "(无)"}
作者: {article.byline or "(无)"}
段落数: {len(article.paragraphs)}

正文:
{paragraphs_text}
"""

    async def translate_batch(
        self,
        articles: list[Article],
        include_vocabulary: bool = True,
        vocabulary_count: int = 10,
    ) -> list[TranslatedArticle]:
        """
        批量翻译多篇文章 - 一次 API 调用处理所有文章
        """
        if not articles:
            return []

        self.logger.info(
            f"Batch translating {len(articles)} articles in ONE API call..."
        )

        # 构建批量提示词
        articles_content = "\n".join(
            [
                self._format_article_for_prompt(article, i + 1)
                for i, article in enumerate(articles)
            ]
        )

        if include_vocabulary:
            prompt = BATCH_TRANSLATION_PROMPT.format(
                article_count=len(articles),
                articles_content=articles_content,
                vocabulary_count=vocabulary_count,
            )
        else:
            prompt = BATCH_TRANSLATION_PROMPT_NO_VOCAB.format(
                article_count=len(articles),
                articles_content=articles_content,
            )

        # 估算需要的输出 token 数
        # 每篇文章大约需要 4000-5000 输出 token（翻译 + 词汇）
        # 无词汇模式通常可减少约 30%-40% 输出
        estimated_tokens_per_article = 5000 if include_vocabulary else 3200
        min_tokens = 20000 if include_vocabulary else 12000
        estimated_tokens = len(articles) * estimated_tokens_per_article
        max_output_tokens = min(
            max(estimated_tokens, min_tokens), 100000
        )  # Flash 模型支持较大输出

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
                self.logger.warning(
                    f"Warning: No translation found for article {i + 1}: {article.title[:30]}..."
                )
                continue

            # 组合双语段落
            paragraphs_cn = article_result.get("paragraphs_cn", [])
            paragraphs = []
            for j, en in enumerate(article.paragraphs):
                cn = paragraphs_cn[j] if j < len(paragraphs_cn) else ""
                paragraphs.append({"en": en, "cn": cn})

            vocabulary = (
                article_result.get("vocabulary", []) if include_vocabulary else []
            )
            vocab_count = len(vocabulary)
            para_translated = sum(1 for p in paragraphs if p.get("cn"))
            if include_vocabulary:
                self.logger.info(
                    f"Article {i + 1}: {para_translated}/{len(paragraphs)} paragraphs, {vocab_count} vocab"
                )
            else:
                self.logger.info(
                    f"Article {i + 1}: {para_translated}/{len(paragraphs)} paragraphs, vocab skipped"
                )

            translated_articles.append(
                TranslatedArticle(
                    title=article.title,
                    title_cn=article_result.get("title_cn", ""),
                    subhead=article.subhead,
                    subhead_cn=article_result.get("subhead_cn", ""),
                    byline=article.byline,
                    byline_cn=article_result.get("byline_cn", ""),
                    paragraphs=paragraphs,
                    vocabulary=vocabulary,
                    original_url=article.url,
                    date=article.date,
                )
            )

        self.logger.info(
            f"Batch complete: {len(translated_articles)}/{len(articles)} articles translated"
        )
        return translated_articles

    async def translate_article(
        self,
        article: Article,
        include_vocabulary: bool = True,
        vocabulary_count: int = 10,
    ) -> TranslatedArticle:
        """
        翻译单篇文章（备用方法）
        """
        self.logger.info(f"Translating single article: {article.title[:50]}...")

        paragraphs_text = "\n\n".join(
            [f"[段落{i + 1}] {p}" for i, p in enumerate(article.paragraphs)]
        )

        if include_vocabulary:
            prompt = SINGLE_TRANSLATION_PROMPT.format(
                title=article.title,
                subhead=article.subhead or "(无)",
                byline=article.byline or "(无)",
                paragraphs=paragraphs_text,
                para_count=len(article.paragraphs),
                vocabulary_count=vocabulary_count,
            )
        else:
            prompt = SINGLE_TRANSLATION_PROMPT_NO_VOCAB.format(
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

        vocabulary = result.get("vocabulary", []) if include_vocabulary else []
        vocab_count = len(vocabulary)
        if include_vocabulary:
            self.logger.info(
                f"Done: {len(paragraphs)} paragraphs, {vocab_count} vocab items"
            )
        else:
            self.logger.info(f"Done: {len(paragraphs)} paragraphs, vocab skipped")

        return TranslatedArticle(
            title=article.title,
            title_cn=result.get("title_cn", ""),
            subhead=article.subhead,
            subhead_cn=result.get("subhead_cn", ""),
            byline=article.byline,
            byline_cn=result.get("byline_cn", ""),
            paragraphs=paragraphs,
            vocabulary=vocabulary,
            original_url=article.url,
            date=article.date,
        )


async def translate_articles(
    articles: list[Article],
    include_vocabulary: bool = True,
    vocabulary_count: int = 10,
) -> list[TranslatedArticle]:
    """
    翻译文章列表 - 全部并行调用（Gemini 2.5 Flash RPM=1000，无需限速）
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
        logger.info(f"Translating {len(articles)} articles in parallel...")

        async def translate_one(article: Article) -> TranslatedArticle | None:
            try:
                return await translator.translate_article(
                    article,
                    include_vocabulary=include_vocabulary,
                    vocabulary_count=vocabulary_count,
                )
            except Exception as e:
                logger.error(f"Failed to translate '{article.title[:60]}': {e}")
                return None

        results = await asyncio.gather(*[translate_one(a) for a in articles])
        all_translated = [r for r in results if r is not None]
        logger.info(f"Done: {len(all_translated)}/{len(articles)} articles translated")
        return all_translated
    finally:
        await translator.close()
