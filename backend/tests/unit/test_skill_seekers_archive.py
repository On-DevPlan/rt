"""Unit tests for skill_seekers 打包导出（page_to_markdown / slug / build_docs_archive）。"""

import zipfile
from io import BytesIO

from rt_backend.skill_seekers.service import (
    _slug_for,
    archive_filename,
    build_docs_archive,
    page_to_markdown,
)


def _page(url: str, title: str = "页", **kw) -> dict:
    page = {
        "url": url,
        "title": title,
        "headings": [{"level": "h2", "text": "小节"}],
        "content": "正文段落。",
        "code_samples": [{"code": "print(1)", "language": "python", "confidence": 0.8}],
        "patterns": [],
        "links": ["https://x.com/next"],
    }
    page.update(kw)
    return page


class TestSlugFor:
    def test_path_derived(self):
        used: set = set()
        assert _slug_for("https://x.com/docs/guide/intro", used) == "docs-guide-intro"

    def test_conflict_gets_counter(self):
        used: set = set()
        a = _slug_for("https://x.com/docs/intro", used)
        b = _slug_for("https://y.com/other/intro", used)  # 尾段同 intro? 不,路径不同
        assert a != b or True
        # 直接构造同路径冲突
        used2: set = set()
        s1 = _slug_for("https://x.com/a", used2)
        s2 = _slug_for("https://x.com/a", used2)
        assert s1 == "a" and s2 == "a-2"

    def test_unsafe_chars_replaced(self):
        used: set = set()
        slug = _slug_for("https://x.com/a b?c=1", used)
        assert " " not in slug and "?" not in slug


class TestPageToMarkdown:
    def test_full_render(self):
        md = page_to_markdown(_page("https://x.com/guide", "指南"))
        assert md.startswith("# 指南")
        assert "> source: https://x.com/guide" in md
        assert "## 小节" in md
        assert "```python" in md and "print(1)" in md
        assert "## Links" in md and "- https://x.com/next" in md

    def test_bad_heading_level_falls_back(self):
        md = page_to_markdown(_page("https://x.com/a", headings=[{"level": "h?", "text": "T"}]))
        assert "## T" in md

    def test_patterns_rendered(self):
        md = page_to_markdown(
            _page("https://x.com/a", patterns=[{"description": "用法", "code": "run()"}])
        )
        assert "- 用法" in md and "```" in md and "run()" in md


class TestBuildDocsArchive:
    def test_zip_structure(self):
        result = {
            "base_url": "https://x.com/docs/",
            "pages_scraped": 2,
            "pages_saved": 2,
            "limit_hit": False,
            "discovered_via_sitemap": 1,
            "discovered_via_llms_txt": 0,
            "pages": [
                _page("https://x.com/docs/a", "页A"),
                _page("https://x.com/docs/b", "页B"),
            ],
            "categories": {"guide": ["https://x.com/docs/a"]},
            "quick_reference": [{"description": "qr", "code": "run()"}],
        }
        zf = zipfile.ZipFile(BytesIO(build_docs_archive(result)))
        names = zf.namelist()
        assert "README.md" in names
        assert "pages/docs-a.md" in names and "pages/docs-b.md" in names
        assert "categories.json" in names and "quick_reference.md" in names
        readme = zf.read("README.md").decode()
        assert "pages/docs-a.md" in readme and "页A" in readme
        assert "run()" in zf.read("quick_reference.md").decode()

    def test_dry_run_pages_excluded(self):
        result = {
            "base_url": "https://x.com/",
            "pages": [_page("https://x.com/a"), {"url": "https://x.com/dry", "dry_run": True}],
        }
        zf = zipfile.ZipFile(BytesIO(build_docs_archive(result)))
        page_files = [n for n in zf.namelist() if n.startswith("pages/")]
        assert page_files == ["pages/a.md"]


def test_archive_filename():
    name = archive_filename("https://platform.example.com/docs/developer-guides/")
    assert name.startswith("docs-platform.example.com_docs-developer-guides_")
    assert name.endswith(".zip")
