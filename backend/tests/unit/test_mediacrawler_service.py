"""Unit tests for mediacrawler service 纯函数（高亮剥除）。"""

from rt_backend.mediacrawler.service import _strip_highlight


class TestStripHighlight:
    """搜索结果标题的 <em> 高亮标签剥除。"""

    def test_keyword_em_class(self):
        assert _strip_highlight('<em class="keyword">python</em> 教程') == "python 教程"

    def test_em_with_attributes(self):
        assert _strip_highlight("a<em class=\"x y\">b</em>c") == "abc"

    def test_no_em(self):
        assert _strip_highlight("普通标题") == "普通标题"

    def test_multiple_em(self):
        assert _strip_highlight("<em>a</em><em>b</em>") == "ab"

    def test_empty_string(self):
        assert _strip_highlight("") == ""
