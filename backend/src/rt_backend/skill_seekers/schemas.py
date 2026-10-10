"""Pydantic schemas for the skill_seekers module."""
from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    base_url: str = Field(description="起始 URL，爬取范围限定在该 URL 目录前缀内")
    max_pages: int = Field(default=10, ge=1, le=50, description="最多抓取页数（防滥用上限 50）")
    rate_limit: float = Field(default=0.2, ge=0, le=10, description="每页间隔秒数")
    include_patterns: list[str] = Field(default=[], description="URL 必须命中的子串（任一）")
    exclude_patterns: list[str] = Field(default=[], description="URL 命中即排除的子串")
    selector: str | None = Field(default=None, description="正文 CSS selector，缺省走内置回退链")
    use_sitemap: bool = Field(default=True, description="先探测 sitemap.xml 发现页面")
    use_llms_txt: bool = Field(default=True, description="sitemap 无结果时探测 llms.txt 发现页面")
    dry_run: bool = Field(default=False, description="只做链接发现，不保存正文")


class Heading(BaseModel):
    level: str
    text: str


class CodeSample(BaseModel):
    code: str
    language: str = ""


class PageData(BaseModel):
    url: str
    title: str = ""
    headings: list[Heading] = []
    content: str = ""
    code_samples: list[CodeSample] = []
    links: list[str] = []


class DryRunPage(BaseModel):
    url: str
    links: list[str]
    dry_run: bool = True


class ScrapeResponse(BaseModel):
    base_url: str
    dry_run: bool
    discovered_via_sitemap: int
    discovered_via_llms_txt: int = 0
    pages_scraped: int
    pages_saved: int
    skipped: int
    elapsed_sec: float
    pages: list[PageData | DryRunPage]
