"""Documentation-site crawler core logic.

Extracted from ``.claude/repo/Skill_Seekers`` 的 ``doc_scraper.py``
（DocToSkillConverter）并精简改写为 httpx.AsyncClient 版本：

- 三层发现引擎的 Layer 1：sitemap.xml 探测（``_try_sitemap``）
- BFS 抓取主循环：pending_urls 队列 + visited/enqueued 双 set O(1) 去重
- URL 规范化：去 #fragment、去跟踪参数（utm_*/fbclid），保留有意义 query
- URL 有效性：base_url 目录前缀 + include/exclude 子串 pattern
- 正文提取：config selector → FALLBACK_MAIN_SELECTORS 回退链（不回退 body）
- 整页 DOM 收集链接（不限正文区），代码块/标题/段落抽取

未迁移（重量级/与 Web 场景无关）：llms.txt 层、Playwright SPA 渲染层、
checkpoint 断点续传、多线程/asyncio 并行、SKILL.md 构建管线。
"""
import asyncio
import logging
import time
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode

import httpx

logger = logging.getLogger(__name__)

# 与原仓库 doc_scraper.py 的 FALLBACK_MAIN_SELECTORS 对齐的回退链
FALLBACK_MAIN_SELECTORS = [
    "main",
    "article",
    '[role="main"]',
    "#content",
    ".content",
    ".markdown-body",
    ".post-content",
    ".documentation",
    ".docs-content",
]

_TRACKING_PARAMS = {"fbclid", "gclid", "msclkid"}
_TRACKING_PREFIXES = ("utm_",)

DEFAULT_RATE_LIMIT = 0.5  # 秒/页（原仓库 DEFAULT_RATE_LIMIT）
SITEMAP_PROBE_TIMEOUT = 5.0


class ScraperError(Exception):
    """skill_seekers 模块错误基类。"""


# ---------------------------------------------------------------------------
# URL 规范化与校验（doc_scraper.py: _normalize_url / is_valid_url）
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """去 #fragment、去跟踪参数，保留有意义 query（如 ?lang=）。"""
    parsed = urlparse(url)
    keep = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in _TRACKING_PARAMS and not k.startswith(_TRACKING_PREFIXES)
    ]
    query = urlencode(keep)
    path = parsed.path or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}{'?' + query if query else ''}"


def _base_dir_of(base_url: str) -> str:
    """取 base_url 的目录前缀：末段像文件（带扩展名）则取其所在目录，
    否则视为目录本身。原仓库 is_valid_url 注释的语义
    （".../docs/index.html" → ".../docs/"，兄弟页可命中）。"""
    if base_url.endswith("/"):
        return base_url
    last = base_url.rsplit("/", 1)[-1]
    if "." in last:  # index.html / a.md 之类 → 当作文件
        return base_url[: base_url.rfind("/") + 1]
    return base_url + "/"


def is_valid_url(url: str, base_url: str, include: list[str], exclude: list[str]) -> bool:
    """base_url 目录前缀内 + 命中 include + 不命中 exclude（原仓库语义）。"""
    if not url.startswith(_base_dir_of(base_url)):
        return False
    if include and not any(p in url for p in include):
        return False
    return not any(p in url for p in exclude)


# ---------------------------------------------------------------------------
# sitemap 发现（doc_scraper.py: _try_sitemap 的 Layer 1）
# ---------------------------------------------------------------------------


def _parse_sitemap_locs(xml_text: str) -> list[str]:
    """解析 sitemap XML 里的 <loc>（含 sitemap index 的 <sitemap><loc>）。"""
    import xml.etree.ElementTree as ET

    locs: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return locs
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]  # 忽略命名空间
        if tag == "loc" and elem.text:
            locs.append(elem.text.strip().split("#")[0])
    return locs


async def try_sitemap(client: httpx.AsyncClient, base_url: str) -> list[str]:
    """探测 domain 根的 sitemap.xml / sitemap_index.xml，返回发现的 URL 列表。"""
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    for sitemap_url in (f"{domain}/sitemap.xml", f"{domain}/sitemap_index.xml"):
        try:
            resp = await client.get(sitemap_url, timeout=SITEMAP_PROBE_TIMEOUT)
            if resp.status_code != 200:
                continue
            if "xml" not in resp.headers.get("content-type", ""):
                continue
            locs = _parse_sitemap_locs(resp.text)
            if locs:
                logger.info("sitemap %s: %d urls", sitemap_url, len(locs))
                return list(set(locs))
        except Exception as e:  # noqa: BLE001 — 探测失败静默降级（原仓库行为）
            logger.debug("sitemap check failed for %s: %s", sitemap_url, e)
    return []


# ---------------------------------------------------------------------------
# 内容提取（doc_scraper.py: _find_main_content / extract_content）
# ---------------------------------------------------------------------------


def find_main_content(soup: Any, selector: str | None) -> Any:
    """config selector → 回退链；不回退到 <body>（原仓库设计）。"""
    if selector:
        main = soup.select_one(selector)
        if main:
            return main
    for sel in FALLBACK_MAIN_SELECTORS:
        main = soup.select_one(sel)
        if main:
            return main
    return None


def extract_content(soup: Any, url: str, selector: str | None = None) -> dict[str, Any]:
    """提取标题/headings/段落/代码块 + 整页链接（原仓库语义：链接收集不限正文区）。"""
    page: dict[str, Any] = {
        "url": url,
        "title": "",
        "headings": [],
        "content": "",
        "code_samples": [],
        "links": [],
    }

    title_elem = soup.select_one("title")
    if title_elem:
        page["title"] = title_elem.get_text(strip=True)

    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(url, str(a.get("href") or "")).split("#")[0]
        href = normalize_url(href)
        if href and href not in seen:
            seen.add(href)
            page["links"].append(href)

    main = find_main_content(soup, selector)
    if main is None:
        return page

    for h in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = h.get_text(strip=True)
        if text:
            page["headings"].append({"level": h.name, "text": text})

    for code in main.select("pre code"):
        text = code.get_text()
        if len(text.strip()) > 10:
            # 语言取 class 里的 language-xxx（原仓库 detect_language 的简版）
            classes = " ".join(code.get("class") or [])
            lang = ""
            for cls in classes.split():
                if cls.startswith("language-"):
                    lang = cls[len("language-"):]
                    break
            page["code_samples"].append({"code": text.strip()[:2000], "language": lang})

    paragraphs = []
    for p in main.find_all("p"):
        text = p.get_text(strip=True)
        if text and len(text) > 20:  # 原仓库：跳过过短段落
            paragraphs.append(text)
    page["content"] = "\n\n".join(paragraphs)

    return page


# ---------------------------------------------------------------------------
# BFS 主循环（doc_scraper.py: scrape_all）
# ---------------------------------------------------------------------------


async def _fetch_and_extract(
    client: httpx.AsyncClient, url: str, selector: str | None, discover_only: bool
) -> dict[str, Any]:
    """抓一页；discover_only（dry-run）只返回链接不解析正文。"""
    resp = await client.get(url, timeout=30.0)
    resp.raise_for_status()
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "html.parser")
    if discover_only:
        links = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(url, str(a.get("href") or "")).split("#")[0]
            href = normalize_url(href)
            if href and href not in seen:
                seen.add(href)
                links.append(href)
        return {"url": url, "links": links, "dry_run": True}
    return extract_content(soup, url, selector)


async def scrape_docs(
    client: httpx.AsyncClient,
    base_url: str,
    max_pages: int = 10,
    rate_limit: float = DEFAULT_RATE_LIMIT,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    selector: str | None = None,
    use_sitemap: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """文档站爬取：sitemap 发现（可选）+ BFS 抓取，返回页面 JSON 列表。

    参数语义与原仓库 doc_scraper 对齐：max_pages 截断、rate_limit 限速、
    include/exclude 子串过滤、dry_run 只做链接发现。
    """
    include = include_patterns or []
    exclude = exclude_patterns or []
    base_url = normalize_url(base_url)

    pending: deque[str] = deque()
    visited: set[str] = set()
    enqueued: set[str] = set()

    def enqueue(url: str) -> None:
        url = normalize_url(url)
        if url not in visited and url not in enqueued:
            enqueued.add(url)
            pending.append(url)

    enqueue(base_url)
    sitemap_count = 0
    if use_sitemap:
        for url in await try_sitemap(client, base_url):
            if is_valid_url(url, base_url, include, exclude):
                enqueue(url)
        sitemap_count = len(pending) - 1

    pages: list[dict[str, Any]] = []
    skipped = 0
    while pending and len(visited) < max_pages:
        url = pending.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            data = await _fetch_and_extract(client, url, selector, discover_only=dry_run)
        except Exception as e:  # noqa: BLE001 — 单页失败不中断爬取（原仓库行为）
            logger.warning("scrape failed %s: %s", url, e)
            skipped += 1
            continue

        for link in data["links"]:
            if is_valid_url(link, base_url, include, exclude):
                enqueue(link)

        if dry_run:
            pages.append(data)  # 只含 url/links 的发现记录
        elif not (data.get("content") or data.get("code_samples")):
            skipped += 1  # 空内容页计数不保存（原仓库 pages_skipped 语义）
        else:
            pages.append(data)

        if rate_limit > 0:
            await asyncio.sleep(rate_limit)

    return {
        "base_url": base_url,
        "dry_run": dry_run,
        "discovered_via_sitemap": sitemap_count,
        "pages_scraped": len(visited),
        "pages_saved": 0 if dry_run else len(pages),
        "skipped": skipped,
        "pages": pages,
        "elapsed_sec": None,  # 由 router 层填充
    }


def started_at() -> float:
    return time.time()
