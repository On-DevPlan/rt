# mediacrawler — 多平台爬虫能力 API（范围克制版）

**API 前缀**：`/api/mediacrawler`　**来源仓库**：`.claude/repo/MediaCrawler`

## 功能作用

MediaCrawler 是 Playwright 多平台爬虫（xhs/douyin/kuaishou/bilibili/weibo/tieba/zhihu），
完整链路 = 浏览器登录 + 平台 client + 数据存储，重量级且强登录依赖，**不适合整体进 rt 后端**
（后端无浏览器托管、无登录会话管理）。本模块按「免登录可用的核心能力」原则做克制包装：

| 能力 | 原实现 | 本模块实现 |
|---|---|---|
| B 站关键词搜索视频 | `media_platform/bilibili/client.py: search_video_by_keyword`（`/x/web-interface/wbi/search/type` + WBI 签名） | `service.py: search_bilibili_videos`，WBI 签名**跨模块复用** `bilibili_crawler.service.sign_params` |
| 平台能力矩阵 | `config/base_config.py` 平台列表 + 各平台登录要求 | `GET /platforms`（哪些平台已包装、哪些需要浏览器登录态） |

**明确不做**（与原仓库的差异）：不用 Playwright 取 cookie（改为可选传 SESSDATA）；
xhs/douyin/kuaishou/weibo/tieba/zhihu 需要浏览器登录签名的平台不包装——请求对应平台时
`/search` 只支持 bilibili，能力边界由 `/platforms` 端点自描述。

搜索结果的 `<em class="keyword">` 高亮标签会被剥除；`result_type != "video"` 的块被过滤。

## 路由表

| 方法 | 路径 | 参数 | 响应 |
|---|---|---|---|
| GET | `/platforms` | — | 7 个平台的 `{name, login_required, playwright_required, wrapped, note}` |
| POST | `/search` | body: `{keyword, page=1, page_size=20(≤50), order=default, pubtime_begin_s=0, pubtime_end_s=0, sessdata?}` | `{keyword, page, num_results, items[]}` |

`order` 取值对齐原仓库 `SearchOrderType`：`default`（综合）/ `click`（最多点击）/
`pubdate`（最新发布）/ `dm`（弹幕最多）/ `stow`（最多收藏）。

错误映射：`-101` → 401；`-412`/`-352`/`-403` 风控 → 502（提示提供 SESSDATA；**先自动失效 WBI key 缓存换新 key 重试一次**）；其他非 0 code → 502。

## curl 案例

```bash
# 1. 看能力矩阵：哪些平台能用、哪些需要登录
curl "http://127.0.0.1:8080/api/mediacrawler/platforms"
# → {"platforms":[{"name":"bilibili","login_required":false,"playwright_required":false,
#     "wrapped":true,"note":"关键词搜索已包装..."},
#    {"name":"xhs","login_required":true,"wrapped":false,...}]}

# 2. B 站关键词搜索（免登录，建议带 SESSDATA 降风控）
curl -X POST "http://127.0.0.1:8080/api/mediacrawler/search" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "python 教程", "page": 1, "page_size": 20, "order": "click"}'
# → {"keyword":"python 教程","page":1,"num_results":1234,"items":[
#     {"aid":1,"bvid":"BV1xx411c7mD","title":"python 教程","author":"up1",
#      "play":100,"danmaku":5,"pubdate":1700000000,...}]}

# 3. 按最新发布排序 + 时间窗过滤
curl -X POST "http://127.0.0.1:8080/api/mediacrawler/search" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "fastapi", "order": "pubdate",
       "pubtime_begin_s": 1735689600, "pubtime_end_s": 1767225600}'
```

## 测试

```bash
cd backend && uv run pytest tests/router/test_mediacrawler_router.py tests/e2e -v
```

上游用 respx 拦截；e2e 验证跨模块 WBI 签名链路（mediacrawler → bilibili_crawler.service）。

## 已知限制

- 搜索接口风控较敏感：无 cookie 时可能 -412（→502），生产使用建议传 `sessdata`
- 其余 6 平台未包装（需浏览器登录态）；如需支持，方向是独立登录会话服务而非塞进本后端
