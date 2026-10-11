# bilibili_crawler — B 站爬虫 API

**API 前缀**：`/api/bilibili-crawler`　**来源仓库**：`.claude/repo/Bilibili_crawler`

## 功能作用

把 Bilibili_crawler 仓库（原为 requests 脚本集）的核心抓取能力包装成 HTTP 服务：

| 能力 | 原脚本 | 本模块实现 |
|---|---|---|
| WBI 签名 | `b站使用wbi签名的爬取方式.py`（mixinKeyEncTab + md5） | `service.py: enc_wbi / sign_params`，nav 接口的 img/sub key **同 client 实例内 1 小时缓存**（`WeakKeyDictionary` + asyncio.Lock 双检），签名扇出不再逐请求打 nav（防风控）；签名请求遇风控自动失效缓存换 key 重试一次（`_signed_get_json`） |
| av↔bv 互转 | `bv2oid.py`（NEWBV 编码） | `service.py: av2bv / bv2av`，纯计算 |
| 视频完整详情 | `MediaCrawler get_video_info`（`/x/web-interface/view/detail`，aid/bvid 二选一、免签名） | `service.py: fetch_video_detail`，含分P `pages[]`（page/part/cid）与合作视频 `staff[]`/`is_cooperation` |
| 播放直链 + 清晰度 | `MediaCrawler get_video_play_url` + `BilibiliDownloader baseModels getQualities/getPlayurl` | `service.py: fetch_play_url`，WBI 签名 playurl（avid/cid/qn/fnval/platform），qn 语义表见 schemas |
| 分P弹幕 | `BilibiliDownloader dmApi`（`/x/v1/dm/list.so?oid={cid}`，上游只落盘原始 XML） | `service.py: fetch_danmaku`，按 B 站标准 dm XML 解析为 `{time, mode, text}` |
| 两级评论爬取 | `Bilibili_crawler.py`（reply/main 分页 + reply/reply 楼中楼） | `service.py: fetch_comments`，字段抽取与原脚本对齐（昵称/性别/时间/点赞/评论/IP属地/等级/uid/rpid） |
| UP 主动态列表 | `bili_user_space.py`（feed/space offset 翻页） | `service.py: fetch_user_space`，抽取 comment_id_str/comment_type 对 |
| UP 主全量投稿 | `MediaCrawler client.py: get_creator_videos`（`/x/space/wbi/arc/search` + WBI） | `service.py: fetch_user_videos`，pn/ps/order（pubdate/click/stow），全部投稿含非动态化条目 |

错误映射：上游 `code=-101` → 401；风控（HTTP 412 / code -352/-403/-412，`RiskControlError`）→ 502——签名链路会先自动失效 WBI key 缓存换新 key 重试一次；其他非 0 code → 502。

## 路由表

| 方法 | 路径 | 参数 | 响应 |
|---|---|---|---|
| POST | `/wbi/sign` | body: `{"params": {...任意业务参数}}` | `w_rid`/`wts`/`signed_params`/`query` |
| GET | `/convert` | query: `aid` 或 `bvid`（二选一） | `{aid, bvid}` |
| GET | `/video/{video_id}` | 路径: aid（纯数字）或 bvid（BV 开头）；query: `sessdata?` | 标题/UP 主/统计 + `pages[]`（分P cid） |
| POST | `/play-url` | body: `{aid, cid, qn=80, fnval=1, fourk=true, sessdata?}` | `{quality, format, accept_quality[], accept_description[], durl[], dash}` |
| GET | `/danmaku/{cid}` | 路径: 分P cid | `{cid, total, items:[{time, mode, text}]}` |
| POST | `/comments` | body: `{oid, type=1, ps=20, pages=1, include_replies=true, mode=3, sessdata?}` | 规范化评论列表（含楼中楼；置顶评论置顶并带 `pinned: true`，按 rpid 去重） |
| POST | `/user-space` | body: `{mid, max_pages=3, sessdata?}` | 动态列表（comment_id_str/comment_type/title） |
| POST | `/user-videos` | body: `{mid, pn=1, ps=30, order=pubdate, sessdata?}` | 全量投稿列表（aid/bvid/title/created/play/video_review/length + count 总数） |
| POST | `/comments/archive` | body: `{oid, type=1, ps=20, include_replies=true, mode=3, max_pages=100(≤200), sessdata?}` | **zip 下载**：README.md + comments.json + comments.md；贪心翻到上游 is_end（`X-Archive-Items`=条数，limit_hit=被上限截断） |
| POST | `/user-videos/archive` | body: `{mid, ps=30, order=pubdate, max_pn=20(≤100), sessdata?}` | **zip 下载**：README.md + videos.json + videos.md 表格；贪心翻到 count 覆盖完 |

## curl 案例

```bash
# 1. av↔bv 互转（纯计算，无需网络）
curl "http://127.0.0.1:8080/api/bilibili-crawler/convert?aid=170001"
# → {"aid":170001,"bvid":"BV17x411w7KC"}

# 2. 视频完整详情（含分P cid）
curl "http://127.0.0.1:8080/api/bilibili-crawler/video/BV1xx411c7mD"
# → {"bvid":"BV1xx411c7mD","aid":170001,"cid":9001,"pages":[{"page":1,"part":"P1","cid":9001}],...}

# 3. 播放直链（aid/cid 来自 /video 响应；直链下载需带 B 站 Referer）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/play-url"   -H "Content-Type: application/json"   -d '{"aid": 170001, "cid": 9001, "qn": 80}'
# → {"quality":80,"format":"mp4","accept_quality":[116,80,32,16],"durl":[{"url":"http://cdn/...","size":...}]}

# 4. 分P弹幕
curl "http://127.0.0.1:8080/api/bilibili-crawler/danmaku/9001"
# → {"cid":9001,"total":88,"items":[{"time":10.5,"mode":1,"text":"..."}]}

# 5. 两级评论（视频评论区 oid=aid；动态评论区 type=17）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/comments" \
  -H "Content-Type: application/json" \
  -d '{"oid": "1504733402", "type": 1, "pages": 2, "include_replies": true}'
# → {"oid":"1504733402","type":1,"total":42,"items":[
#      {"rpid":"...","name":"...","time":"2023-11-15 08:00:00","like":5,
#       "message":"...","location":"北京","level":3,"mid":"...","replies":[...]}]}

# 6. WBI 签名（拿到 w_rid/wts 后可自行请求任意需要签名的 B 站接口）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/wbi/sign" \
  -H "Content-Type: application/json" \
  -d '{"params": {"oid": 1504733402, "type": 1, "mode": 3}}'
# → {"w_rid":"<32位hex>","wts":1791619340,"signed_params":{...},"query":"oid=...&w_rid=..."}

# 7. UP 主动态（返回可爬评论的 oid/type 对）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/user-space" \
  -H "Content-Type: application/json" \
  -d '{"mid": "42", "max_pages": 3}'
# → {"mid":"42","total":25,"items":[{"comment_id_str":"111","comment_type":1,"title":"..."}]}

# 8. UP 主全量投稿（动态 feed 的补集：含置顶隐藏、非动态化投稿）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/user-videos" \
  -H "Content-Type: application/json" \
  -d '{"mid": "42", "order": "click"}'
# → {"mid":"42","count":88,"total":30,"items":[{"aid":170001,"bvid":"BV17x411w7KC","title":"...","play":500}]}
```

## 测试

```bash
cd backend && uv run pytest tests/test_bilibili_crawler_router.py -v
```

上游接口全部用 respx 拦截（不依赖外网与真实 cookie）。

## 已知限制

- 评论翻页无登录态时部分页可能被风控（412 → 502，提示提供 SESSDATA）
- `ps` 上限 30（Pydantic 校验）、`pages` 上限 20，防止接口被滥用拖垮后端
