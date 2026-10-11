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
    categorize: bool = Field(
        default=False, description="聚合开关：响应附带 categories（3/2/1 关键词打分归类）与 quick_reference"
    )
    categories: dict[str, list[str]] | None = Field(
        default=None,
        description="分类配置 {分类名: [关键词...]}；缺省走 URL 段推断（段频 Top8、≥3 页、tutorials/api 兜底）",
    )


class Heading(BaseModel):
    level: str
    text: str


class CodeSample(BaseModel):
    code: str = Field(default="", description="代码文本（HTML 与 .md 路径统一截断到 2000 字符）")
    language: str = ""
    confidence: float = Field(default=0.0, description="语言判定置信度（class 命中=1.0）")


class PatternItem(BaseModel):
    description: str = ""
    code: str


class QuickRefItem(BaseModel):
    description: str
    code: str


class PageData(BaseModel):
    url: str
    title: str = ""
    headings: list[Heading] = []
    content: str = ""
    code_samples: list[CodeSample] = []
    patterns: list[PatternItem] = []
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
    limit_hit: bool = Field(
        default=False, description="True=已抓满 max_pages 上限，结果可能不是站点全量"
    )
    pages_saved: int
    skipped: int
    elapsed_sec: float
    pages: list[PageData | DryRunPage]
    categories: dict[str, list[str]] | None = Field(
        default=None, description="categorize=true 时返回：{分类名: [url,...]}"
    )
    quick_reference: list[QuickRefItem] | None = Field(
        default=None, description="categorize=true 时返回：跨页 patterns 去重聚合（≤15）"
    )


class ArchiveScrapeRequest(BaseModel):
    """递归抓取并打包为 zip 下载（服务端渲染 markdown，每页一文件）。"""

    base_url: str = Field(description="起始 URL（要整站就填文档根，如 https://x.com/docs/）")
    scope: str = Field(
        default="auto",
        pattern="^(auto|strict)$",
        description="范围语义：auto=起始页是无扩展名叶子（如 .../introduction）时自动放宽到其所在目录（抓同目录兄弟页）；strict=严格 base_url 目录前缀（原仓库语义）",
    )
    max_pages: int = Field(default=50, ge=1, le=200, description="最多抓取页数（打包场景放宽到 200；串行+rate_limit 注意耗时）")
    rate_limit: float = Field(default=0.2, ge=0, le=10, description="每页间隔秒数")
    include_patterns: list[str] = Field(default=[], description="URL 必须命中的子串（任一）；注意会把范围再收窄")
    exclude_patterns: list[str] = Field(default=[], description="URL 命中即排除的子串（如 deprecated/blog）")
    selector: str | None = Field(default=None, description="正文 CSS selector，缺省走内置回退链")
    use_sitemap: bool = Field(default=True, description="先探测 sitemap.xml 发现页面")
    use_llms_txt: bool = Field(default=True, description="sitemap 无结果时探测 llms.txt 发现页面")
    categorize: bool = Field(default=True, description="压缩包内附带 categories.json / quick_reference.md")
    categories: dict[str, list[str]] | None = Field(
        default=None, description="分类配置 {分类名: [关键词...]}；缺省走 URL 段推断"
    )
