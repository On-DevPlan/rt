"""Unit tests for skill_seekers service 纯函数（URL 规范化/校验、sitemap 解析、正文提取）。"""
from bs4 import BeautifulSoup

from rt_backend.skill_seekers.service import (
    FALLBACK_MAIN_SELECTORS,
    _parse_sitemap_xml,
    extract_content,
    find_main_content,
    is_valid_url,
    normalize_url,
    parse_llms_txt_links,
)


class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://e.com/docs/a#section") == "https://e.com/docs/a"

    def test_drops_tracking_params_keeps_meaningful(self):
        url = "https://e.com/p?utm_source=x&fbclid=1&lang=zh&id=3"
        assert normalize_url(url) == "https://e.com/p?lang=zh&id=3"

    def test_utmx_prefix_all_variants(self):
        url = "https://e.com/p?utm_medium=y&notutm=z&keep=1"
        assert normalize_url(url) == "https://e.com/p?notutm=z&keep=1"


class TestIsValidUrl:
    BASE = "https://e.com/docs/"

    def test_prefix_scoped_to_base_dir(self):
        assert is_valid_url("https://e.com/docs/a", self.BASE, [], [])
        assert not is_valid_url("https://e.com/api/a", self.BASE, [], [])
        # 兄弟目录不算
        assert not is_valid_url("https://e.com/docsx/a", self.BASE, [], [])

    def test_include_exclude_substring(self):
        assert is_valid_url("https://e.com/docs/guide/x", self.BASE, ["guide"], [])
        assert not is_valid_url("https://e.com/docs/api/x", self.BASE, ["guide"], [])
        assert not is_valid_url("https://e.com/docs/guide/old", self.BASE, [], ["old"])


class TestSitemapParsing:
    def test_namespaced_urlset(self):
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://e.com/a</loc></url>
          <url><loc>https://e.com/b#frag</loc></url>
        </urlset>"""
        children, pages = _parse_sitemap_xml(xml)
        assert children == []
        assert pages == ["https://e.com/a", "https://e.com/b"]

    def test_sitemap_index(self):
        xml = """<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://e.com/sitemap-1.xml</loc></sitemap>
        </sitemapindex>"""
        children, pages = _parse_sitemap_xml(xml)
        assert children == ["https://e.com/sitemap-1.xml"]
        assert pages == []

    def test_index_with_own_urls_both_collected(self):
        """索引文档自身含 <url> 时两者叠加（原仓库对同一 root 两遍 findall 的语义）。"""
        xml = """<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://e.com/sm-1.xml</loc></sitemap>
          <url><loc>https://e.com/root-page</loc></url>
        </sitemapindex>"""
        children, pages = _parse_sitemap_xml(xml)
        assert children == ["https://e.com/sm-1.xml"]
        assert pages == ["https://e.com/root-page"]

    def test_invalid_xml_returns_empty(self):
        assert _parse_sitemap_xml("not xml at all <<<") == ([], [])


class TestLlmsTxtParsing:
    def test_markdown_links_extracted(self):
        text = """# Docs

- [快速开始](https://e.com/docs/start): 入门
- [API 参考](https://e.com/docs/api "title 属性")
- 非链接行
"""
        assert parse_llms_txt_links(text) == [
            "https://e.com/docs/start",
            "https://e.com/docs/api",
        ]

    def test_no_links_returns_empty(self):
        assert parse_llms_txt_links("# only heading\nplain text") == []

    def test_relative_links_ignored(self):
        # 发现层只收绝对 URL（原仓库 downloader 语义），相对路径交给 BFS 链接扩展
        assert parse_llms_txt_links("[rel](/docs/x)") == []


_HTML = """
<html><head><title>文档页</title></head><body>
<nav><a href="/docs/b">B页</a><a href="https://ext.com/x">外链</a></nav>
<article>
  <h1>标题</h1><h2>小节</h2>
  <p>这是一个足够长的段落，超过二十个字符的阈值，所以会被保留下来。</p>
  <p>短</p>
  <pre><code class="language-python">print("hello world example")</code></pre>
  <a href="/docs/c?utm_source=t">C页</a>
</article>
</body></html>
"""


class TestExtractContent:
    def test_full_extraction(self):
        soup = BeautifulSoup(_HTML, "html.parser")
        page = extract_content(soup, "https://e.com/docs/a")

        assert page["title"] == "文档页"
        assert page["headings"] == [
            {"level": "h1", "text": "标题"},
            {"level": "h2", "text": "小节"},
        ]
        # 短段落被跳过
        assert "足够长的段落" in page["content"] and "短" not in page["content"]
        # 代码块带语言
        assert page["code_samples"][0]["language"] == "python"
        # 链接来自整页（nav 里的也算），去 fragment、去跟踪参数、拼绝对路径
        assert "https://e.com/docs/b" in page["links"]
        assert "https://e.com/docs/c" in page["links"]  # utm 被去掉
        assert "https://ext.com/x" in page["links"]

    def test_fallback_selector_chain(self):
        # 无 <article> 时回退到回退链里的 #content
        html = _HTML.replace("<article>", '<div id="content">').replace("</article>", "</div>")
        soup = BeautifulSoup(html, "html.parser")
        main = find_main_content(soup, None)
        assert main is not None
        assert main.get("id") == "content"

    def test_config_selector_wins(self):
        soup = BeautifulSoup(_HTML.replace("article", "section"), "html.parser")
        main = find_main_content(soup, "section")
        assert main is not None and main.name == "section"

    def test_no_main_content_returns_links_only(self):
        soup = BeautifulSoup("<html><body><p>hi</p></body></html>", "html.parser")
        page = extract_content(soup, "https://e.com/x")
        assert page["content"] == ""
        assert page["headings"] == []

    def test_fallback_constants_match_upstream(self):
        # 与 Skill_Seekers doc_scraper 的回退语义一致：不包含 body
        assert "body" not in FALLBACK_MAIN_SELECTORS
        assert FALLBACK_MAIN_SELECTORS[0] == "main"


# ---------------------------------------------------------------------------
# loop-2 第 3 轮：patterns / 低信号 / 描述规范化 / .md 解析 / 分类聚合
# ---------------------------------------------------------------------------

from rt_backend.skill_seekers.service import (  # noqa: E402
    clean_text,
    extract_markdown_page,
    extract_patterns,
    generate_quick_reference,
    infer_categories,
    is_low_signal_code_snippet,
    normalize_pattern_description,
    smart_categorize,
)
from bs4 import BeautifulSoup  # noqa: E402


class TestLowSignal:
    def test_blacklist_exact(self):
        assert is_low_signal_code_snippet("success=false")
        assert is_low_signal_code_snippet("None")

    def test_single_identifier(self):
        assert is_low_signal_code_snippet("getUserById")

    def test_scalar_assign(self):
        assert is_low_signal_code_snippet("x = 42")
        assert is_low_signal_code_snippet('name = "hello"')

    def test_short_single_line_no_structure(self):
        assert is_low_signal_code_snippet("justtext")

    def test_real_code_passes(self):
        assert not is_low_signal_code_snippet("def f(x):\n    return x + 1")
        assert not is_low_signal_code_snippet("obj.method().chain()")


class TestNormalizePatternDescription:
    def test_strips_numbering_and_prefix(self):
        assert normalize_pattern_description("1. Example: create a client") == "create a client"

    def test_first_sentence(self):
        assert (
            normalize_pattern_description("Usage: Make the thing. Then more words here.")
            == "Make the thing."
        )

    def test_junk_returns_none(self):
        assert normalize_pattern_description("Example:") is None
        assert normalize_pattern_description("42") is None
        assert normalize_pattern_description("short") is None

    def test_truncation(self):
        out = normalize_pattern_description("x" * 200)
        assert out is not None and len(out) == 150 and out.endswith("...")


class TestCleanText:
    def test_folds_whitespace(self):
        assert clean_text("  a\n\nb\t c  ") == "a b c"


class TestExtractPatterns:
    def _soup(self, body: str):
        return BeautifulSoup(body, "html.parser")

    def test_usage_paragraph_yields_pattern(self):
        html = """
        <article>
          <p>Usage: create a client with the base url.</p>
          <pre><code class="language-python">client = Client(base_url)</code></pre>
        </article>
        """
        patterns = extract_patterns(self._soup(html).select_one("article"))
        assert len(patterns) == 1
        assert patterns[0]["description"] == "create a client with the base url."
        assert "Client(base_url)" in patterns[0]["code"]

    def test_low_signal_code_skipped(self):
        html = """
        <article>
          <p>Example: an option.</p>
          <pre><code>true</code></pre>
        </article>
        """
        assert extract_patterns(self._soup(html).select_one("article")) == []

    def test_cap_five(self):
        blocks = "".join(
            f"<p>Usage: pattern number {i} with enough words.</p>"
            f"<pre><code>def f{i}():\n    return {i}</code></pre>"
            for i in range(8)
        )
        patterns = extract_patterns(self._soup(f"<article>{blocks}</article>"))
        assert len(patterns) == 5


class TestMarkdownPage:
    MD = """# 标题在此
## 安装

正文第一段，长度必须超过二十个字符才能被保留下来哦。

正文第二段，同样需要超过二十个字符的长度阈值。

```python
print("hello world sample")
```

[下一章](./next.md) [外站](https://other.com/x.md)
"""

    def test_full_extraction(self):
        page = extract_markdown_page(self.MD, "https://e.com/docs/readme.md", lambda u: True)
        assert page["title"] == "标题在此"
        assert page["headings"] == [{"level": "h2", "text": "安装"}]
        assert "正文第一段" in page["content"]
        assert page["code_samples"][0]["language"] == "python"
        # 原版规则：仅保留 .md 结尾且 is_valid 的链接（外站 .md 也保留）
        assert page["links"] == [
            "https://e.com/docs/next.md",
            "https://other.com/x.md",
        ]

    def test_invalid_md_link_filtered(self):
        page = extract_markdown_page(self.MD, "https://e.com/docs/readme.md", lambda u: False)
        assert page["links"] == []


def _page(url: str, title: str, content: str) -> dict:
    return {"url": url, "title": title, "content": content, "patterns": []}


class TestCategorize:
    def test_url_score_three_and_threshold(self):
        pages = [
            _page("https://e.com/guide/a", "任意", "x" * 30),
            _page("https://e.com/guide/b", "任意", "x" * 30),
            _page("https://e.com/api/c", "任意", "x" * 30),
        ]
        cats = smart_categorize(pages, categories={"guide": ["guide"], "api": ["api"]})
        assert cats["guide"] == [
            "https://e.com/guide/a",
            "https://e.com/guide/b",
        ]
        assert cats["api"] == ["https://e.com/api/c"]

    def test_other_fallback_when_below_threshold(self):
        pages = [_page("https://e.com/misc/a", "无关键词", "x" * 30)]
        cats = smart_categorize(pages, categories={"guide": ["guide"]})
        assert cats == {"other": ["https://e.com/misc/a"]}

    def test_infer_categories_segments(self):
        pages = [
            _page("https://e.com/guide/x", "", "") for _ in range(3)
        ] + [_page("https://e.com/api/y", "", "") for _ in range(3)]
        cats = infer_categories(pages)
        assert cats.get("guide") == ["guide"]
        assert cats.get("api") == ["api"]


class TestQuickReference:
    def test_dedup_and_limit(self):
        pattern = {"description": "create a client.", "code": "c = Client()"}
        pages = [{**_page(f"https://e.com/{i}", "t", "x" * 30), "patterns": [pattern]} for i in range(20)]
        qr = generate_quick_reference(pages)
        assert len(qr) == 1  # 同码去重

    def test_cap_fifteen(self):
        pages = []
        for i in range(20):
            pages.append(
                {
                    **_page(f"https://e.com/{i}", "t", "x" * 30),
                    "patterns": [{"description": f"desc number {i} here.", "code": f"code_{i} = make({i})"}],
                }
            )
        qr = generate_quick_reference(pages)
        assert len(qr) == 15
