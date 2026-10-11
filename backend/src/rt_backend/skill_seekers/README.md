# skill_seekers — 文档站爬虫 API

**API 前缀**：`/api/skill-seekers`　**来源仓库**：`.claude/repo/Skill_Seekers`

## 功能作用

把 Skill_Seekers 仓库 `doc_scraper.py`（DocToSkillConverter，BFS 文档站爬虫）的核心抓取
逻辑包装成 HTTP 服务。原仓库用爬到的文档生成 AI skill 包；本模块提供其中「抓取」这一段，
返回页面 JSON，构建 skill 的部分交给调用方。

已迁移的核心逻辑（对照原文件）：

| 能力 | 原实现 | 本模块实现 |
|---|---|---|
| sitemap.xml 发现（三层发现引擎 Layer 1） | `_try_sitemap` | `service.py: try_sitemap`（探测 sitemap.xml / sitemap_index.xml，忽略命名空间解析 `<loc>`） |
| llms.txt 发现（三层发现引擎 Layer 2） | `_try_llms_txt` | `service.py: try_llms_txt`（sitemap 无结果时探测 `domain/llms.txt`，提取 markdown 链接并入 BFS） |
| BFS 主循环 | `scrape_all` | `service.py: scrape_docs`（deque 队列 + visited/enqueued 双 set O(1) 去重） |
| URL 规范化 | `_normalize_url` + sanitize | `normalize_url`（去 #fragment、去 utm_*/fbclid/gclid/msclkid，保留有意义 query 如 ?lang=） |
| URL 有效性 | `is_valid_url` | `is_valid_url`（base_url **目录前缀** + include/exclude 子串；index.html 取所在目录，兄弟页可命中） |
| 正文提取 | `extract_content` + `_find_main_content` | `extract_content`（selector → 9 级回退链，**不回退 body**；整页 DOM 收集链接；标题/headings/代码块/段落） |
| patterns 抽取 | `extract_patterns`（4 关键词 + 邻近 pre + 低信号过滤 + 上限5） | `service.py: extract_patterns`，每页 `patterns[]`（描述已规范化） |
| 语言启发式 | `language_detector`（class 置信度 1.0 / 关键词计分兜底） | `service.py: detect_language_heuristic`（精简 8 语言），`code_samples[].confidence` |
| .md 直链解析 | `_has_md_extension` + `_extract_markdown_content` legacy 规则 | `service.py: extract_markdown_page`（仅保留 .md 链接的爬取语义） |
| 分类聚合 | `smart_categorize`（URL+3/标题+2/正文+1、阈值2、max 归属、other 兜底）+ `infer_categories`（段频 Top8/≥3 次）+ `generate_quick_reference`（去重 ≤15） | `scrape_docs(categorize=true)` → 响应 `categories` / `quick_reference` |
| 空内容页 | pages_skipped 计数 | `skipped` 字段（<20 字符段落过滤与原仓库一致） |

**未迁移**（重量级/与 Web 服务场景无关，见总文档决策记录）：Playwright SPA 渲染层
（原三层引擎的 Layer 3）、checkpoint 断点续传、多线程/asyncio 并行抓取、SKILL.md 构建管线。

**与原仓库的偏差**：原仓库 llms.txt 命中后直接下载其内容并跳过 HTML 爬取；本模块为保持
统一响应结构，把 llms.txt 当作 URL 发现源并入 BFS（llms.txt 里的链接通常就是文档页）。

## 路由表

| 方法 | 路径 | 参数 | 响应 |
|---|---|---|---|
| POST | `/scrape` | body: `{base_url, max_pages=10(≤50), rate_limit=0.2, include_patterns[], exclude_patterns[], selector?, use_sitemap=true, use_llms_txt=true, dry_run=false, categorize=false, categories?}` | `{base_url, dry_run, discovered_via_sitemap, discovered_via_llms_txt, pages_scraped, limit_hit（已抓满 max_pages，结果可能非全量）, pages_saved, skipped, elapsed_sec, pages[], categories?, quick_reference?}` |
| POST | `/scrape/archive` | body: `{base_url, scope=auto(auto=叶子起始页放宽到所在目录/strict=严格目录前缀), max_pages=50(≤200), rate_limit=0.2, include_patterns[], exclude_patterns[], selector?, use_sitemap=true, use_llms_txt=true, categorize=true, categories?}` | **zip 二进制下载**：`README.md` 索引 + `pages/*.md`（每页标题/正文/代码块/链接）+ `categories.json` / `quick_reference.md`；响应头 `X-Scrape-Pages` 为入库页数 |

`pages[]` 元素：正常页 `{url, title, headings[], content, code_samples[], links[]}`；
dry-run 页 `{url, links[], dry_run: true}`（仍会抓页做链接发现，原仓库语义）。

`max_pages` 是硬上限（服务端再卡 50），防止接口被拿来无限制爬站。

## curl 案例

```bash
# 1. 基本爬取：从文档站首页 BFS 抓 10 页
curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://docs.example.com/guide/", "max_pages": 10}'
# → {"base_url":"https://docs.example.com/guide/","discovered_via_sitemap":24,
#    "pages_scraped":10,"pages_saved":9,"skipped":1,"elapsed_sec":4.2,
#    "pages":[{"url":"...","title":"快速开始","headings":[{"level":"h1","text":"快速开始"}],
#              "content":"段落文本…","code_samples":[{"code":"npm install","language":"bash"}],
#              "links":["..."]}]}

# 2. 只抓 URL 含 /v2/ 的页面，排除 deprecated：
curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://docs.example.com/v2/", "max_pages": 30,
       "include_patterns": ["/v2/"], "exclude_patterns": ["deprecated", "/blog/"]}'

# 3. dry-run：只看会抓到哪些页（每页仍会 GET 做链接发现）
curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://docs.example.com/", "dry_run": true}'
# → pages 里是 {url, links[], dry_run: true} 的发现记录，pages_saved=0

# 4. 指定正文 selector（SPA 站点正文区域不规则时）
curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://docs.example.com/", "selector": "div.theme-doc-markdown"}'

# 5. 递归抓完直接打包 zip 下载（每页一个 markdown + 索引 + 分类）
curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape/archive" \
  -H "Content-Type: application/json" -o docs-archive.zip \
  -d '{"base_url": "https://docs.example.com/docs/", "max_pages": 100}'
# → docs-docs.example.com_docs_-2026-10-11.zip
#   ├─ README.md            # 索引（base_url/计数/每页链接表）
#   ├─ pages/*.md           # 每页一个 markdown（标题/source/正文/代码块/链接）
#   ├─ categories.json      # categorize=true 时
#   └─ quick_reference.md   # categorize=true 时
```

## 测试

```bash
cd backend
uv run pytest tests/unit/test_skill_seekers_service.py -v      # 纯函数层
uv run pytest tests/router/test_skill_seekers_router.py -v     # 路由层（respx）
uv run pytest tests/e2e -v                                     # 真实 app + 本地 fixture 站点
```

路由层用 respx 拦截上游；e2e 层起本地 fixture 文档站走真 HTTP 回环。

## 已知限制

- 不执行 JS：SPA 站点需要原仓库的 Playwright 渲染层（未迁移），纯服务端渲染站点可用
- 串行抓取 + rate_limit，50 页上限，面向「查文档/小规模快照」而非全站镜像
