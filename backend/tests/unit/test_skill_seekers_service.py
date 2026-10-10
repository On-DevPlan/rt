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
