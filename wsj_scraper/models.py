"""
数据模型 - 与业务逻辑解耦的纯数据类
"""

import hashlib
from dataclasses import dataclass, asdict


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
