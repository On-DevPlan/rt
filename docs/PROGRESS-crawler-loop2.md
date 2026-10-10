# 爬虫模块差距补全循环 — loop-2 进度文件

> Ralph 循环 loop-2（5 轮，无完成承诺）。每轮协议：恢复上下文 → sub agent 差距分析 →
> 实现 1-3 个最高价值项 → pytest 全绿 + build → 更新本文件 → commit。
> 前置成果见 docs/PROGRESS-crawler-webapi.md（loop-1，已完结）。

## 状态

| 轮次 | sub agent 报告 | 实现项 | 验证 | commit |
|---|---|---|---|---|
| 1 | ✅ 12 条差距（Top3：置顶评论+排序 / 视频元数据包 / UP 全量投稿） | Top1 + Top3 + 测试补充 | ✅ 264/0 + build | ✅ |
| 2 | ✅ 上游行为实证（A-E 五节：view/playurl/弹幕XML/sitemap递归/md解析） | 视频元数据包（#4+#2+#10）+ sitemap index 递归（#7） | ✅ 269/0 + build | ✅ |
| 3 | ✅ doc_scraper 增值特征规则实证（patterns/低信号/描述规范化/分类/quick_ref/SKILL 管线边界） | .md 解析（#8）+ patterns/语言启发式（#6 页级）+ categorize 聚合开关 | ✅ 290/0 + build | ✅ |
| 4 | ⏳（建议：HTTP 重试退避（#9）+ cookbook 场景补齐与语义标签（#11）） | — | — | — |
| 5 | 未开始 | | | |

## 第 1 轮记录（2026-10-11，commit 2fbb126）

**sub agent 报告结论**：核心链路已完备，前端 specs ↔ schemas 无字段缺口。12 条差距按价值排序：
置顶评论缺失(高) / playurl+清晰度(高) / UP 全量投稿(高) / view-detail+分P(中) / 评论排序(中) /
doc_scraper patterns+分类(中) / sitemap index 不递归(中) / .md 直链解析(中) / HTTP 重试(中) /
弹幕(中) / cookbook 覆盖 6/14(中) / bilibili_crawler 测试缺口(低)。

**本轮实现**（差距 #1、#5、#3、#12）：
1. `bilibili_crawler` 置顶评论：`_extract_pinned_replies`（top_replies + top dict/list 混合形态）+ `pinned` 字段 + rpid 去重
2. `CommentsRequest.mode` 排序参数（0/1/2/3 透传上游）
3. 新端点 `POST /user-videos`：WBI 签名的 `/x/space/wbi/arc/search`（pubdate/click/stow）
4. 测试 +7（置顶去重/mode 透传/412→502/include_replies=false/楼中楼多页/user-videos 签名/非法 order）
5. 闭环同步：前端 specs + landing + README + cookbook §1/§3.6

**验证**：264 passed / 0 failed（+7）；`pnpm build` 通过。

## 第 3 轮记录（2026-10-11）

**sub agent 报告结论**（9 节实证）：patterns 关键词 4 清单（example:/pattern:/usage:/typical use
子串匹配）；低信号五条判定（黑名单/单标识符/裸赋值/短单行无结构）；描述规范化七步（剥编号/
前缀/首句/垃圾判定/150 截断）；smart_categorize 3-2-1 打分 + 阈值 2 + max 唯一归属 + other 兜底；
infer_categories 段频计数 Top8 + ≥3 次门槛 + tutorials/api 兜底；quick_ref 折叠代码去重 + <300 +
上限 15；references/SKILL.md 生成属构建管线不进 API（agent 明确建议）。

**本轮实现**（差距 #8、#6）：
1. `.md` 直链解析：`extract_markdown_page`（title=# 行 / headings=#{2,6} / fenced code>10 /
   content 去码后 >20 字符段 / links 仅 .md 且 is_valid）+ BFS 分支（path.endswith(".md")）
2. patterns 页级抽取：`extract_patterns`（4 关键词 → find_next(pre) → 低信号过滤 → 描述规范化 → ≤5）
3. 语言启发式兜底：`detect_language_heuristic`（8 语言关键词计分，confidence=min(score/10,1)，<0.5→unknown），
   `code_samples[].confidence` 新字段
4. categorize 聚合开关：`ScrapeRequest.categorize/categories` → 响应 `categories`/`quick_reference`
   （smart_categorize + infer_categories + generate_quick_reference 全套原版语义）
5. 测试 +21（低信号 5/描述规范化 4/clean_text/patterns 3/md 2/分类 3/quick_ref 2 + router categorize 聚合）
6. 闭环同步：specs（categorize/categories 输入）、README 功能表与路由表、cookbook §3.5 返回解读

**验证**：backend pytest **290 passed / 0 failed**（+21）；`pnpm build` 通过。

**下轮建议**：HTTP 重试指数退避（#9，在 core/http 或 _get_json 包装，2-3 次退避仅 5xx/412，
respx side_effect 模拟 502→200）+ cookbook 场景补齐与 order/quality 语义标签（#11）。

## 第 2 轮记录（2026-10-11）

**sub agent 报告结论**（A-E 实证）：
- view/detail：aid/bvid 二选一、免签名、View 包装；pages[] 字段 page/cid 实证（part 为标准字段）
- playurl：`/x/player/wbi/playurl` WBI 签名，参数名 **avid**（非 aid）、qn 默认 80、fnval 1=mp4 合一/4048=DASH、platform=pc；qn 全语义表（116→16）
- 弹幕：`/x/v1/dm/list.so?oid={cid}`，**上游仓库只落盘原始 XML 无解析代码**（解析按 B 站标准 dm 格式）
- sitemap index：固定一层递归、索引自身 url 叠加收集、命中候选即返回
- .md 解析：path.endswith(".md") 触发，legacy 兜底规则齐全（title/frontmatter、h2-h6、fenced code、≥20 字符段）——留作下轮

**本轮实现**（差距 #4、#2、#10、#7）：
1. `GET /video/{video_id}` 升级：aid/bvid 自适应 + view/detail + `pages[]`（分P cid）+ pic/cid 字段
2. 新端点 `POST /play-url`：WBI 签名 playurl（avid/cid/qn/fnval/fourk/platform），durl 直链 + accept_quality 清晰度表，qn 语义进 schemas description
3. 新端点 `GET /danmaku/{cid}`：XML 解析为 `{time, mode, text}`（UpstreamError 包装解析失败）
4. `try_sitemap` 重写：索引型递归一层 + 自身 url 叠加 + set 去重（`_parse_sitemap_xml` 返回 (children, pages) 元组）
5. 测试 +5（video 升级/aid 自适应/invalid 422/play-url 签名与 durl/danmaku XML/sitemap 索引递归）+ unit sitemap 契约更新（含混合索引新用例）
6. 闭环同步：前端 specs（video 自适应 + play-url 卡 + danmaku 卡）、landing 8 端点、README 路由表与 curl 重排、cookbook §1 速查 + 新场景 3.7

**验证**：backend pytest **269 passed / 0 failed**（+5）；`pnpm build` 通过。

**下轮建议**：.md 直链 markdown 解析（#8，报告 E 节 legacy 规则可直接照抄：title/# 标题/fenced code/≥20 字符段/links .md 过滤）+ doc_scraper patterns 抽取与语言启发式兜底（#6）。次选：cookbook 场景覆盖补齐（#11：wbi/sign、favorites/add、playlist/user songs、platforms + order/quality 语义标签）。

## 遗留候选（sub agent 报告未实现项，供后续轮次）

- [ ] HTTP 重试指数退避（#9，动 core/http.py 需回归全部模块）
- [ ] cookbook 场景覆盖补齐 + order/quality 语义标签（#11）
- [ ] 收藏夹旧接口 /x/space/fav/arc 兼容开关（loop-1 遗留，低优先）
