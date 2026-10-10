# 爬虫模块差距补全循环 — loop-2 进度文件

> Ralph 循环 loop-2（5 轮，无完成承诺）。每轮协议：恢复上下文 → sub agent 差距分析 →
> 实现 1-3 个最高价值项 → pytest 全绿 + build → 更新本文件 → commit。
> 前置成果见 docs/PROGRESS-crawler-webapi.md（loop-1，已完结）。

## 状态

| 轮次 | sub agent 报告 | 实现项 | 验证 | commit |
|---|---|---|---|---|
| 1 | ✅ 12 条差距（Top3：置顶评论+排序 / 视频元数据包 / UP 全量投稿） | Top1 + Top3 + 测试补充 | ✅ 264/0 + build | ✅ |
| 2 | ⏳（建议聚焦：视频元数据包 playurl+弹幕+view/detail） | — | — | — |
| 3-5 | 未开始 | | | |

## 第 1 轮记录（2026-10-11）

**sub agent 报告结论**：核心链路已完备，前端 specs ↔ schemas 无字段缺口。12 条差距按价值排序：
置顶评论缺失(高) / playurl+清晰度(高) / UP 全量投稿(高) / view-detail+分P(中) / 评论排序(中) /
doc_scraper patterns+分类(中) / sitemap index 不递归(中) / .md 直链解析(中) / HTTP 重试(中) /
弹幕(中) / cookbook 覆盖 6/14(中) / bilibili_crawler 测试缺口(低)。

**本轮实现**（差距 #1、#5、#3、#12）：
1. `bilibili_crawler` 置顶评论：`_extract_pinned_replies`（top_replies + top dict/list 混合形态，
   对齐原仓库 Bilibili_crawler.py 与 MediaCrawler 语义）+ `pinned` 字段 + rpid 去重
2. `CommentsRequest.mode` 排序参数（0/1/2/3 透传上游）
3. 新端点 `POST /user-videos`：WBI 签名的 `/x/space/wbi/arc/search`（pubdate/click/stow），
   补齐 cookbook 3.6 承诺的「全量投稿」链路（动态 feed 的补集）
4. 测试 +7：置顶去重/mode 透传/412→502/include_replies=false/楼中楼多页 ceil/user-videos 签名/非法 order
5. 闭环同步：前端 specs（comments mode select + user-videos 卡片）、landing 端点数、
   bilibili_crawler README、cookbook §1 速查 + §3.6 重写

**验证**：backend pytest **264 passed / 0 failed**（+7）；`pnpm build` 通过。

**下轮建议**：视频元数据包（报告 #4+#2+#10）：`/video/{id}` 升级 view/detail + aid 入参 + `pages[]/cid`
→ `POST /play-url`（WBI 签名 playurl，qn/accept_quality/durl）→ `GET /danmaku/{cid}`（XML 解析）。
次选：sitemap index 递归（#7）+ .md 直链解析（#8）。

## 遗留候选（sub agent 报告未实现项，供后续轮次）

- [ ] 视频元数据包：view/detail + playurl + 弹幕（#4/#2/#10，建议轮 2）
- [ ] sitemap index 递归抓子 sitemap（#7）
- [ ] .md 直链页面 markdown 解析（#8）
- [ ] doc_scraper patterns/语言启发式/smart_categorize 聚合开关（#6）
- [ ] HTTP 重试指数退避（#9，动 core/http.py 需回归全部模块）
- [ ] cookbook 场景覆盖 6/14 → 补 wbi/sign、favorites/add、playlist、platforms 场景 + order/quality 语义标签（#11）
