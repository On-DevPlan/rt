# bilibili_crawler — B 站爬虫 API

**API 前缀**：`/api/bilibili-crawler`　**来源仓库**：`.claude/repo/Bilibili_crawler`

## 功能作用

把 Bilibili_crawler 仓库（原为 requests 脚本集）的核心抓取能力包装成 HTTP 服务：

| 能力 | 原脚本 | 本模块实现 |
|---|---|---|
| WBI 签名 | `b站使用wbi签名的爬取方式.py`（mixinKeyEncTab + md5） | `service.py: enc_wbi / sign_params`，实时取 nav 接口的 img/sub key |
| av↔bv 互转 | `bv2oid.py`（NEWBV 编码） | `service.py: av2bv / bv2av`，纯计算 |
| 视频元信息 | `Bilibili_crawler.py`（view 接口） | `service.py: fetch_video_info` |
| 两级评论爬取 | `Bilibili_crawler.py`（reply/main 分页 + reply/reply 楼中楼） | `service.py: fetch_comments`，字段抽取与原脚本对齐（昵称/性别/时间/点赞/评论/IP属地/等级/uid/rpid） |
| UP 主动态列表 | `bili_user_space.py`（feed/space offset 翻页） | `service.py: fetch_user_space`，抽取 comment_id_str/comment_type 对 |
| UP 主全量投稿 | `MediaCrawler client.py: get_creator_videos`（`/x/space/wbi/arc/search` + WBI） | `service.py: fetch_user_videos`，pn/ps/order（pubdate/click/stow），全部投稿含非动态化条目 |

错误映射：上游 `code=-101` → 401；其他非 0 code / 风控 412 → 502。

## 路由表

| 方法 | 路径 | 参数 | 响应 |
|---|---|---|---|
| POST | `/wbi/sign` | body: `{"params": {...任意业务参数}}` | `w_rid`/`wts`/`signed_params`/`query` |
| GET | `/convert` | query: `aid` 或 `bvid`（二选一） | `{aid, bvid}` |
| GET | `/video/{bvid}` | 路径: BV 号 | 标题/UP 主/播放/点赞等统计 |
| POST | `/comments` | body: `{oid, type=1, ps=20, pages=1, include_replies=true, mode=3, sessdata?}` | 规范化评论列表（含楼中楼；置顶评论置顶并带 `pinned: true`，按 rpid 去重） |
| POST | `/user-space` | body: `{mid, max_pages=3, sessdata?}` | 动态列表（comment_id_str/comment_type/title） |
| POST | `/user-videos` | body: `{mid, pn=1, ps=30, order=pubdate, sessdata?}` | 全量投稿列表（aid/bvid/title/created/play/length + count 总数） |

## curl 案例

```bash
# 1. av↔bv 互转（纯计算，无需网络）
curl "http://127.0.0.1:8080/api/bilibili-crawler/convert?aid=170001"
# → {"aid":170001,"bvid":"BV17x411w7KC"}

# 2. 视频信息
curl "http://127.0.0.1:8080/api/bilibili-crawler/video/BV1xx411c7mD"
# → {"bvid":"BV1xx411c7mD","aid":170001,"title":"...","view":1000,"like":60,...}

# 3. 两级评论（视频评论区 oid=aid；动态评论区 type=17）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/comments" \
  -H "Content-Type: application/json" \
  -d '{"oid": "1504733402", "type": 1, "pages": 2, "include_replies": true}'
# → {"oid":"1504733402","type":1,"total":42,"items":[
#      {"rpid":"...","name":"...","time":"2023-11-15 08:00:00","like":5,
#       "message":"...","location":"北京","level":3,"mid":"...","replies":[...]}]}

# 4. WBI 签名（拿到 w_rid/wts 后可自行请求任意需要签名的 B 站接口）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/wbi/sign" \
  -H "Content-Type: application/json" \
  -d '{"params": {"oid": 1504733402, "type": 1, "mode": 3}}'
# → {"w_rid":"<32位hex>","wts":1791619340,"signed_params":{...},"query":"oid=...&w_rid=..."}

# 5. UP 主动态（返回可爬评论的 oid/type 对）
curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/user-space" \
  -H "Content-Type: application/json" \
  -d '{"mid": "42", "max_pages": 3}'
# → {"mid":"42","total":25,"items":[{"comment_id_str":"111","comment_type":1,"title":"..."}]}

# 6. UP 主全量投稿（动态 feed 的补集：含置顶隐藏、非动态化投稿）
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
