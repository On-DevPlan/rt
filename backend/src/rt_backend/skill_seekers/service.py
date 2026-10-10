"""Documentation-site crawler core logic.

Extracted from ``.claude/repo/Skill_Seekers`` 的 ``doc_scraper.py``
（DocToSkillConverter）并精简改写为 httpx.AsyncClient 版本：

- 三层发现引擎的 Layer 1：sitemap.xml 探测（``_try_sitemap``）
- 三层发现引擎的 Layer 2：llms.txt 发现（``_try_llms_txt`` 的发现源化——
  原仓库 llms.txt 命中后直接跳过 HTML 爬取；本模块为保持统一响应结构，
  把 llms.txt 当 URL 发现源并入 BFS。差异记录在模块 README）
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
import re
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


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """解析 sitemap XML，返回 (子 sitemap 地址列表, 页面 URL 列表)。

    忽略命名空间；URL 剥 #fragment。解析失败返回 ([], [])。
    """
    import xml.etree.ElementTree as ET

    children: list[str] = []
    pages: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return children, pages
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]  # 忽略命名空间
        if tag not in ("sitemap", "url"):
            continue
        for sub in elem.iter():
            if sub.tag.rsplit("}", 1)[-1] == "loc" and sub.text:
                loc = sub.text.strip().split("#")[0]
                (children if tag == "sitemap" else pages).append(loc)
    return children, pages


async def try_sitemap(client: httpx.AsyncClient, base_url: str) -> list[str]:
    """探测 domain 根的 sitemap.xml / sitemap_index.xml，返回发现的 URL 列表。

    索引型（含 <sitemap><loc>）时对每个子 sitemap 再拉一次并提取其中的页面
    （固定一层递归，与原仓库 doc_scraper._try_sitemap 一致）；索引文档自身的
    <url><loc> 也叠加收集。命中候选即返回（set 去重）。
    """
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    for sitemap_url in (f"{domain}/sitemap.xml", f"{domain}/sitemap_index.xml"):
        try:
            resp = await client.get(sitemap_url, timeout=SITEMAP_PROBE_TIMEOUT)
            if resp.status_code != 200:
                continue
            if "xml" not in resp.headers.get("content-type", ""):
                continue
            children, pages = _parse_sitemap_xml(resp.text)
            for child in children:
                try:
                    cresp = await client.get(child, timeout=SITEMAP_PROBE_TIMEOUT)
                    if cresp.status_code == 200:
                        _, child_pages = _parse_sitemap_xml(cresp.text)
                        pages.extend(child_pages)
                except Exception as e:  # noqa: BLE001 — 单个子 sitemap 失败不中断（原仓库行为）
                    logger.debug("child sitemap failed %s: %s", child, e)
            if pages:
                logger.info("sitemap %s: %d urls (children=%d)", sitemap_url, len(pages), len(children))
                return list(set(pages))
        except Exception as e:  # noqa: BLE001 — 探测失败静默降级（原仓库行为）
            logger.debug("sitemap check failed for %s: %s", sitemap_url, e)
    return []


# ---------------------------------------------------------------------------
# llms.txt 发现（doc_scraper.py: _try_llms_txt 的 Layer 2）
# ---------------------------------------------------------------------------

_LLMS_TXT_URL = "{domain}/llms.txt"
# [text](url "optional title") —— 允许 markdown 可选 title 部分
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^\s)]+)(?:\s+\"[^\"]*\")?\)")


def parse_llms_txt_links(text: str) -> list[str]:
    """从 llms.txt（markdown 格式）提取全部链接 URL。"""
    return [m.group(1) for m in _MD_LINK_RE.finditer(text)]


async def try_llms_txt(client: httpx.AsyncClient, base_url: str) -> list[str]:
    """探测 domain 根的 llms.txt，返回其中发现的 URL（探测失败静默降级）。"""
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    try:
        resp = await client.get(_LLMS_TXT_URL.format(domain=domain), timeout=SITEMAP_PROBE_TIMEOUT)
        if resp.status_code != 200:
            return []
        links = parse_llms_txt_links(resp.text)
        if links:
            logger.info("llms.txt: %d links", len(links))
        return links
    except Exception as e:  # noqa: BLE001 — 探测失败静默降级（原仓库行为）
        logger.debug("llms.txt check failed for %s: %s", domain, e)
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
    """提取标题/headings/段落/代码块/patterns + 整页链接（原仓库语义：链接收集不限正文区）。"""
    page: dict[str, Any] = {
        "url": url,
        "title": "",
        "headings": [],
        "content": "",
        "code_samples": [],
        "patterns": [],
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
            # 语言：class 优先（Tier 1），否则关键词启发式（Tier 2 精简版）
            classes = " ".join(code.get("class") or [])
            lang = ""
            for cls in classes.split():
                if cls.startswith("language-"):
                    lang = cls[len("language-"):]
                    break
                if cls.startswith("lang-"):
                    lang = cls[len("lang-"):]
                    break
            lang, confidence = detect_language_heuristic(text, css_lang=lang)
            page["code_samples"].append(
                {"code": text.strip()[:2000], "language": lang, "confidence": round(confidence, 2)}
            )

    page["patterns"] = extract_patterns(main)

    paragraphs = []
    for p in main.find_all("p"):
        text = p.get_text(strip=True)
        if text and len(text) > 20:  # 原仓库：跳过过短段落
            paragraphs.append(text)
    page["content"] = "\n\n".join(paragraphs)

    return page


# ---------------------------------------------------------------------------
# 增值特征（doc_scraper.py: patterns / 语言启发式 / clean_text / 分类聚合）
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")

# extract_patterns 的 4 个触发关键词（原 805 行清单，子串匹配、大小写不敏感）
_PATTERN_KEYWORDS = ("example:", "pattern:", "usage:", "typical use")
# _is_low_signal_code_snippet 的黑名单（原 831-841 行）
_LOW_SIGNAL_BLACKLIST = {
    "true", "false", "none", "null", "options", "status_code",
    "success=false", "success=true", "on_page_context_created",
}
_IDENT_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
_SCALAR_ASSIGN_RE = re.compile(r"[a-z_][a-z0-9_]*\s*=\s*(true|false|none|null|-?\d+(\.\d+)?|\"[^\"]*\"|'[^']*')")
_CODE_CHARS = ("(", ".", "[", "{", ":")


def clean_text(text: str) -> str:
    """空白折叠：\\s+ → 单空格，掐头去尾（原 921-923 行）。"""
    return _WHITESPACE_RE.sub(" ", text).strip()


def is_low_signal_code_snippet(code: str) -> bool:
    """低信号代码判定（原 823-861 行，按序）：空 / 黑名单精确命中 / 单标识符 /
    裸标量赋值 / 短单行无结构字符。"""
    folded = clean_text(code)
    if not folded:
        return True
    if folded.lower() in _LOW_SIGNAL_BLACKLIST:
        return True
    if _IDENT_RE.fullmatch(folded):
        return True
    if _SCALAR_ASSIGN_RE.fullmatch(folded.lower()):
        return True
    if "\n" not in code and len(folded) < 16 and not any(ch in code for ch in _CODE_CHARS):
        return True
    return False


def normalize_pattern_description(description: str) -> str | None:
    """pattern 描述规范化（原 863-894 行七步），残留垃圾返回 None。"""
    text = clean_text(description)
    if not text:
        return None
    text = re.sub(r"^\s*\d+[\).:\-\s]+", "", text)  # 剥前导编号
    text = re.sub(r"(example|usage|pattern)\s*:", "", text, flags=re.IGNORECASE)  # 剥前缀
    text = text.strip(" -:")
    if not text:
        return None
    first = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    if len(first) >= 8:
        text = first  # 首句足够长则只用首句
    junk = {"example", "usage", "pattern", "what", "note"}
    if text.lower().strip(" .:") in junk or text.isdigit() or len(text) < 8:
        return None
    if len(text) > 150:
        text = text[:147] + "..."
    return text


# 简版语言启发式（原 detect_language 的 Tier 2 子集：关键词计分，confidence=min(score/10,1)）
_LANG_HINTS: dict[str, tuple[str, ...]] = {
    "python": ("def ", "import ", "from ", "print(", "self.", "__init__"),
    "javascript": ("const ", "let ", "function ", "=>", "console.log", "require("),
    "typescript": (": string", ": number", "interface ", "type ", "export const"),
    "bash": ("#!/bin/", "echo ", "sudo ", "apt ", "$ ", " && "),
    "json": ('": ', "{\n", "[\n"),
    "sql": ("select ", "insert into", "create table", "where "),
    "html": ("<!doctype", "<div", "<span", "</"),
    "css": ("{", "}", ":hover", "px;", "display:"),
}


def detect_language_heuristic(code: str, css_lang: str = "") -> tuple[str, float]:
    """语言检测两级：class 已知 → (lang, 1.0)；否则关键词计分启发式，
    confidence = min(score/10, 1)，< 0.5 归 unknown（原 Tier 2 语义的精简版）。"""
    if css_lang:
        return css_lang, 1.0
    stripped = code.strip()
    if len(stripped) < 10:
        return "unknown", 0.0
    lower = stripped.lower()
    best, best_score = "unknown", 0
    for lang, hints in _LANG_HINTS.items():
        score = sum(lower.count(h.lower()) for h in hints)
        if score > best_score:
            best, best_score = lang, score
    confidence = min(best_score / 10.0, 1.0)
    if confidence < 0.5:
        return "unknown", confidence
    return best, confidence


def extract_patterns(main: Any) -> list[dict[str, str]]:
    """pattern 抽取（原 794-821 行）：4 关键词子串命中的 p/div → 文档序下一个
    pre（内嵌 code 优先）→ 低信号过滤 → 规范化描述 → 上限 5。"""
    patterns: list[dict[str, str]] = []
    for elem in main.find_all(["p", "div"]):
        text = elem.get_text()
        if not any(kw in text.lower() for kw in _PATTERN_KEYWORDS):
            continue
        pre = elem.find_next("pre")
        if pre is None:
            continue
        code_elem = pre.find("code")
        code = (code_elem if code_elem is not None else pre).get_text().strip()
        if not code or is_low_signal_code_snippet(code):
            continue
        description = normalize_pattern_description(text)
        entry = {"code": code}
        if description:
            entry["description"] = description
        patterns.append(entry)
        if len(patterns) >= 5:  # 原仓库 patterns[:5]
            break
    return patterns


def extract_markdown_page(text: str, url: str, is_valid_fn) -> dict[str, Any]:
    """.md 直链解析（原 _extract_markdown_content 的 legacy 兜底规则，632-701 行）。

    title = 首个 "# " 行；headings = #{2,6}；代码 = ```lang\\n...```（>10 字符）；
    content = 去码后按空行切、保留 >20 字符且非 # 开头的段；
    links = markdown 链接 → 绝对化/剥锚点，仅保留 .md 结尾且 is_valid 的（原版语义：
    md 页面只顺着其他 md 链接爬）。
    """
    page: dict[str, Any] = {
        "url": url,
        "title": "",
        "headings": [],
        "content": "",
        "code_samples": [],
        "patterns": [],
        "links": [],
    }

    for line in text.splitlines():
        if line.startswith("# "):
            page["title"] = line[2:].strip()
            break

    for m in re.finditer(r"^(#{2,6})\s+(.+)$", text, re.MULTILINE):
        t = m.group(2).strip()
        page["headings"].append({"level": f"h{len(m.group(1))}", "text": t})

    for m in re.finditer(r"```(\w+)?\n(.*?)```", text, re.DOTALL):
        code = m.group(2)
        if len(code.strip()) > 10:
            page["code_samples"].append(
                {"code": code.strip(), "language": m.group(1) or "unknown"}
            )

    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    paragraphs = [
        seg.strip()
        for seg in no_code.split("\n\n")
        if len(seg.strip()) > 20 and not seg.strip().startswith("#")
    ]
    page["content"] = "\n\n".join(paragraphs)

    seen: set[str] = set()
    # md 链接用全量匹配（原 legacy 规则：任意 href，相对路径 urljoin 绝对化）
    for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
        href = m.group(1)
        if href.startswith("#"):
            continue
        absolute = href if href.startswith("http") else urljoin(url, href)
        absolute = absolute.split("#")[0]
        if absolute in seen:
            continue
        if absolute.endswith(".md") and is_valid_fn(absolute):
            seen.add(absolute)
            page["links"].append(absolute)
    return page


def infer_categories(pages: list[dict[str, Any]]) -> dict[str, list[str]]:
    """无 config 时的 URL 段推断（原 1967-1996 行）：path 段按出现次数计数 Top8、
    ≥3 次门槛、tutorials/api 兜底。"""
    from collections import Counter

    seg_counts: Counter[str] = Counter()
    for p in pages:
        path = urlparse(p.get("url", "")).path
        for seg in path.split("/"):
            if seg and seg not in ("en", "stable", "latest", "docs"):
                seg_counts[seg] += 1
    top = [seg for seg, _ in seg_counts.most_common(8)]
    categories = {seg: [seg] for seg in top if seg_counts[seg] >= 3}
    all_urls = " ".join(p.get("url", "") for p in pages)
    if "tutorial" in all_urls and "tutorials" not in categories:
        categories["tutorials"] = ["tutorial", "guide", "getting-started"]
    if ("api" in all_urls or "reference" in all_urls) and "api" not in categories:
        categories["api"] = ["api", "reference", "class"]
    return categories


def smart_categorize(
    pages: list[dict[str, Any]], categories: dict[str, list[str]] | None = None
) -> dict[str, list[str]]:
    """分类聚合（原 1917-1965 行）：关键词子串打分 URL+3/标题+2/正文+1（正文预览
    500 字符），阈值 ≥2，取最高分唯一归属，无命中归 other，空类剔除。"""
    if not categories:
        categories = infer_categories(pages)
    lowered = {name: [k.lower() for k in kws] for name, kws in categories.items()}
    lowered.setdefault("other", [])
    buckets: dict[str, list[str]] = {name: [] for name in lowered}

    for page in pages:
        url_l = (page.get("url") or "").lower()
        title_l = (page.get("title") or "").lower()
        content_l = (page.get("content") or "").lower()[:500]
        scores = {}
        for name, kws in lowered.items():
            if name == "other" or not kws:
                continue
            score = 0
            for kw in kws:
                if kw in url_l:
                    score += 3
                if kw in title_l:
                    score += 2
                if kw in content_l:
                    score += 1
            scores[name] = score
        best = max(scores, key=lambda n: scores[n]) if scores else "other"
        buckets[best if scores and scores[best] >= 2 else "other"].append(page.get("url", ""))

    return {name: urls for name, urls in buckets.items() if urls}


def generate_quick_reference(pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """quick_reference 聚合（原 1998-2025 行）：跨页 patterns 汇总，规范化描述 +
    折叠代码去重 + len<300 + 非低信号，上限 15。"""
    quick_ref: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for page in pages:
        for pattern in page.get("patterns") or []:
            code = pattern.get("code", "")
            folded = clean_text(code)
            description = normalize_pattern_description(pattern.get("description", ""))
            if (
                description
                and folded
                and folded not in seen_codes
                and len(code) < 300
                and not is_low_signal_code_snippet(code)
            ):
                seen_codes.add(folded)
                quick_ref.append({"description": description, "code": code.strip()})
            if len(quick_ref) >= 15:
                return quick_ref
    return quick_ref


# ---------------------------------------------------------------------------
# BFS 主循环（doc_scraper.py: scrape_all）
# ---------------------------------------------------------------------------


async def _fetch_and_extract(
    client: httpx.AsyncClient,
    url: str,
    selector: str | None,
    discover_only: bool,
    is_valid_fn=None,
) -> dict[str, Any]:
    """抓一页；discover_only（dry-run）只返回链接不解析正文；.md 结尾的 URL 走
    markdown 解析（原仓库 _has_md_extension 分支）。5xx/网络错误自动重试。"""
    from ..core.http import request_with_retry

    resp = await request_with_retry(client, "GET", url, timeout=30.0)
    resp.raise_for_status()
    if urlparse(url).path.endswith(".md"):
        # .md 直链：markdown 解析（原仓库分支），HTML 响应兜底走普通提取
        body = resp.text.lstrip()
        if discover_only:
            page = extract_markdown_page(body, url, is_valid_fn or (lambda u: True))
            return {"url": url, "links": page["links"], "dry_run": True}
        return extract_markdown_page(body, url, is_valid_fn or (lambda u: True))
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
    use_llms_txt: bool = True,
    dry_run: bool = False,
    categorize: bool = False,
    categories: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """文档站爬取：sitemap/llms.txt 发现（可选）+ BFS 抓取，返回页面 JSON 列表。

    发现顺序对齐原仓库三层引擎：Layer 1 sitemap → Layer 2 llms.txt（sitemap
    无结果时才试）。参数语义与原仓库 doc_scraper 对齐：max_pages 截断、
    rate_limit 限速、include/exclude 子串过滤、dry_run 只做链接发现。
    categorize=true 时附带分类聚合（smart_categorize/infer_categories 语义）
    与 quick_reference（跨页 patterns 去重，上限 15）。
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

    def _is_valid(url: str) -> bool:
        return is_valid_url(url, base_url, include, exclude)

    enqueue(base_url)
    sitemap_count = 0
    llms_count = 0
    if use_sitemap:
        for url in await try_sitemap(client, base_url):
            if _is_valid(url):
                enqueue(url)
        sitemap_count = len(pending) - 1
    if use_llms_txt and sitemap_count == 0:
        # Layer 2：sitemap 无结果才试 llms.txt（原仓库优先级语义）
        for url in await try_llms_txt(client, base_url):
            if _is_valid(url):
                enqueue(url)
        llms_count = len(pending) - 1 - sitemap_count

    pages: list[dict[str, Any]] = []
    skipped = 0
    while pending and len(visited) < max_pages:
        url = pending.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            data = await _fetch_and_extract(
                client, url, selector, discover_only=dry_run, is_valid_fn=_is_valid
            )
        except Exception as e:  # noqa: BLE001 — 单页失败不中断爬取（原仓库行为）
            logger.warning("scrape failed %s: %s", url, e)
            skipped += 1
            continue

        for link in data["links"]:
            if _is_valid(link):
                enqueue(link)

        if dry_run:
            pages.append(data)  # 只含 url/links 的发现记录
        elif not (data.get("content") or data.get("code_samples")):
            skipped += 1  # 空内容页计数不保存（原仓库 pages_skipped 语义）
        else:
            pages.append(data)

        if rate_limit > 0:
            await asyncio.sleep(rate_limit)

    result = {
        "base_url": base_url,
        "dry_run": dry_run,
        "discovered_via_sitemap": sitemap_count,
        "discovered_via_llms_txt": llms_count,
        "pages_scraped": len(visited),
        "pages_saved": 0 if dry_run else len(pages),
        "skipped": skipped,
        "pages": pages,
        "categories": None,
        "quick_reference": None,
        "elapsed_sec": None,  # 由 router 层填充
    }
    if categorize and not dry_run and pages:
        result["categories"] = smart_categorize(pages, categories)
        result["quick_reference"] = generate_quick_reference(pages)
    return result


def started_at() -> float:
    return time.time()
