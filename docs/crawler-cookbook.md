# Crawler API Cookbook — 4 个爬虫模块的实用调用手册

> 路径前缀：`/api/{bilibili-crawler, bilibili-tools, skill-seekers, mediacrawler}`
> 模块源码：`backend/src/rt_backend/{name}/`（每模块含 README.md + schemas.py）
> 总迁移文档：`docs/crawler-webapi-migration.md`
> 前端 Explorer：`/crawlers/<name>`（源码 `src/modules/crawlers/`）
> 日期：2026-10-10

---

## 0. 阅读对象与前置

- 想在 5 分钟内拉一批 B 站评论 / 收藏夹 / 音频 CDN 直链 / 文档站快照的人
- 想搞清楚前端 Explorer 页面背后调的是哪个端点、出错时按什么规则排障的人
- 前置：后端已启动
  ```bash
  cd D:/code/a_js/proj/rt/backend
  PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8080
  ```

部署侧提醒：`POST /api/bilibili-tools/favorites/add` 是**写操作**，公网部署务必置于鉴权层后（见 `crawler-webapi-migration.md` §已知限制）。

---

## 1. 端点速查表

| 模块 | 前缀 | GET | POST |
|---|---|---|---|
| bilibili-crawler | `/api/bilibili-crawler` | `convert`、`video/{id}`、`danmaku/{cid}` | `wbi/sign`、`comments`、`user-space`、`user-videos`、`play-url` |
| bilibili-tools | `/api/bilibili-tools` | `favorites`、`audio/{sid}`、`audio/playlist/{sid}`、`audio/user` | `favorites/add` ⚠️写 |
| skill-seekers | `/api/skill-seekers` | — | `scrape` |
| mediacrawler | `/api/mediacrawler` | `platforms` | `search` |

OpenAPI：`http://127.0.0.1:8080/docs`。

---

## 2. 错误信封与排障规则

| 症状 | 含义 | 处理 |
|---|---|---|
| `401`，detail 含 `-101` / `csrf` | 登录态失效或未提供 | 补 SESSDATA（写操作再加 bili_jct） |
| `403`，detail 含「公开」/「权限」 | 私有收藏夹（11004/11010/53013/-403） | 换公开收藏夹 |
| `422` | 参数校验失败（Pydantic） | 看 detail 里的字段路径，对照各模块 schemas.py |
| `502`，detail 含「风控」「412」 | B 站风控拦截 | 带 SESSDATA 重试；降低频率 |
| `502`，其他 | 上游非 0 code | 看 detail 里的上游 code 与 message |
| fetch 直接失败 | 后端没起 | 回到 §0 的启动命令 |

写操作 `/favorites/add` 的逐条结果在响应体 `results[]` 里（`code`/`ok`/`pattern`/`message`），HTTP 层仍 200——只在凭证整体无效时才 401。

---

## 3. 实用场景

### 3.1 B 站视频两级评论抓取

- **场景**：批量分析某视频评论区，要完整结构（含楼中楼）与 IP 属地/等级等字段。
- **端点**：`POST /api/bilibili-crawler/comments`
- **curl**：
  ```bash
  curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/comments" \
    -H "Content-Type: application/json" \
    -d '{"oid": "170001", "type": 1, "pages": 2, "include_replies": true}'
  ```
- **UI**：`/crawlers/bilibili-crawler` → 「两级评论」→ 填 oid + pages → 提交。
- **返回解读**：`items[]` 一级评论；`items[].replies[]` 楼中楼（同构）；`location` 已剥 `IP属地：` 前缀；`is_end` 翻到底标记。
- **常见错误**：`ps` ≤30、`pages` ≤20 越界 → 422；无 cookie 高页数 → 502 风控。

### 3.2 B 站收藏夹导出为 JSON

- **场景**：把一个公开收藏夹拉成离线清单（aid/bvid/标题/封面/失效标记）。
- **端点**：`GET /api/bilibili-tools/favorites`
- **curl**：
  ```bash
  # link 含 ?fid= 与父级 query 冲突，用 -G --data-urlencode 让它整体成为 link 的值
  curl -G "http://127.0.0.1:8080/api/bilibili-tools/favorites" \
    --data-urlencode "link=https://space.bilibili.com/42/favlist?fid=12345" \
    --data-urlencode "limit=50"
  ```
- **写操作示例**（把多个 av 号加进收藏夹，需 SESSDATA + bili_jct）：
  ```bash
  curl -X POST "http://127.0.0.1:8080/api/bilibili-tools/favorites/add" \
    -H "Content-Type: application/json" \
    -d '{"sessdata":"...","bili_jct":"...","fid":"12345","aids":["170001","2"]}'
  # → results[] 逐条 {aid, code, ok, message}；11007/11201=已收藏（ok=true）
  ```
- **UI**：`/crawlers/bilibili-tools` → 「收藏夹枚举」→ 贴完整 favlist 链接 → 提交。
- **返回解读**：`fav_title` 收藏夹名；`items[].state=1` 失效视频；`bvid` 可直接拼 `https://www.bilibili.com/video/{bvid}`。
- **常见错误**：私有收藏夹 → 403；`link` 解析不出 mid/fid → 422（改传 mid+fid）。

### 3.3 B 站音频区单曲拿 CDN 直链

- **场景**：下载某首歌（原 you-get 路线的替代）。
- **端点**：`GET /api/bilibili-tools/audio/{sid}`
- **curl**：
  ```bash
  curl "http://127.0.0.1:8080/api/bilibili-tools/audio/au241921?quality=2"
  ```
- **UI**：`/crawlers/bilibili-tools` → 「单曲信息 + CDN 直链」→ 填 `au241921` → 提交。
- **返回解读**：`cdns[]` 是 m4a 直链（**有时效 + Referer 校验**，下载时 `curl -H "Referer: https://www.bilibili.com/" -o song.m4a <cdn>`）；`lyric` 是 `.lrc` 歌词地址；`cover` 封面图；`quality` 回显生效音质。
- **常见错误**：quality 越界（合法 0=128K / 1=192K / 2=320K）→ 422；直链 403 时补 Referer。

### 3.4 B 站关键词搜索（按点击量找教程）

- **场景**：找某主题的高质量视频，按播放/点击排序。
- **端点**：`POST /api/mediacrawler/search`
- **curl**：
  ```bash
  curl -X POST "http://127.0.0.1:8080/api/mediacrawler/search" \
    -H "Content-Type: application/json" \
    -d '{"keyword": "python 教程", "order": "click", "page_size": 20}'
  ```
- **UI**：`/crawlers/mediacrawler` → 「B 站关键词搜索」→ 填 keyword + order → 提交。
- **返回解读**：`items[].bvid/aid/play/danmaku/pubdate`；标题里的 `<em class="keyword">` 高亮已被剥除；`num_results` 为上游报的总数。
- **常见错误**：无 SESSDATA 时 `-412` 风控 → 502（带上 sessdata 字段）；`order` 非法值 → 422。

### 3.5 文档站快速 BFS 快照

- **场景**：把一个文档站从首页抓 N 页正文 + 代码块，喂 LLM 或存本地快照。
- **端点**：`POST /api/skill-seekers/scrape`
- **curl**：
  ```bash
  curl -X POST "http://127.0.0.1:8080/api/skill-seekers/scrape" \
    -H "Content-Type: application/json" \
    -d '{"base_url": "https://docs.example.com/guide/", "max_pages": 20, "dry_run": true}'
  ```
- **UI**：`/crawlers/skill-seekers` → 填 base_url → 先 `dry_run=true` 看会抓哪些页 → 再关掉 dry_run 实抓。
- **返回解读**：`discovered_via_sitemap/llms_txt` 发现来源计数；`pages_saved` 真正存正文的页数；`skipped` 空内容页；`limit_hit=true` 表示已抓满 max_pages（结果可能不是站点全量）；`pages[].content` 段落文本（>20 字符）、`code_samples[]` 带语言与置信度、`pages[].patterns[]` 是用法示例（Usage/Example 段落 + 邻近代码）。**加 `categorize: true` 可拿聚合结果**：`categories`（{分类: [url]}，可用 `categories` 参数自定义关键词，缺省按 URL 段推断）+ `quick_reference`（跨页去重的高信号用法示例 ≤15 条，适合直接喂 LLM）。
- **常见错误**：50 页硬上限；SPA 站点（正文靠 JS 渲染）抓不到——本模块不执行 JS；`base_url` 的目录前缀决定范围（`.../guide/` 只抓 guide 子树）。

### 3.6 UP 主全量投稿 → 全量视频评论链路

- **场景**：抓某 UP 主**所有投稿**的评论（动态 feed 只是投稿子集——置顶隐藏、非动态化的投稿都拿不到，必须走 arc/search）。
- **端点**：`POST /api/bilibili-crawler/user-videos`（WBI 签名）→ `POST /api/bilibili-crawler/comments`
- **curl**：
  ```bash
  # 第一步：全量投稿列表（翻 pn 直到 count 覆盖完）
  curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/user-videos" \
    -H "Content-Type: application/json" \
    -d '{"mid": "42", "pn": 1, "ps": 30, "order": "pubdate"}'

  # 第二步：逐个视频喂评论端点（type 固定 1，oid 用 aid）
  curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/comments" \
    -H "Content-Type: application/json" \
    -d '{"oid": "<aid>", "type": 1, "pages": 1}'
  ```
- **UI**：`/crawlers/bilibili-crawler` 先「UP 主全量投稿」后「两级评论」，手动接力。
- **返回解读**：user-videos 的 `items[].aid` 即评论端点的 `oid`（type=1）；`count` 是投稿总数（翻页终止条件：`pn * ps >= count`）。补充：`user-space`（动态 feed）适合抓**动态**评论区（type=17），两者互补。
- **常见错误**：order 非法 → 422（pubdate/click/stow）；高频连跑触发风控 → 502，加 SESSDATA + 放慢。评论响应里 `items[].pinned=true` 是置顶评论（已按 rpid 去重，与普通列表重复时只保留置顶份）。

### 3.7 视频直链链路（详情 → 分P cid → 直链 / 弹幕）

- **场景**：拿某视频的播放直链或弹幕内容（元数据三件套：评论 §3.1 / 直链+弹幕本节）。
- **端点**：`GET /api/bilibili-crawler/video/{id}` → `POST /api/bilibili-crawler/play-url` + `GET /api/bilibili-crawler/danmaku/{cid}`
- **curl**：
  ```bash
  # 第一步：视频详情（bvid 或 aid 自适应），拿分P cid
  curl "http://127.0.0.1:8080/api/bilibili-crawler/video/BV1xx411c7mD"

  # 第二步：直链（qn 清晰度；fnval=1 返回 mp4 合一 durl，4048=DASH 无直链）
  curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/play-url" \
    -H "Content-Type: application/json" \
    -d '{"aid": 170001, "cid": 9001, "qn": 80}'

  # 第三步（可选）：该分P的弹幕
  curl "http://127.0.0.1:8080/api/bilibili-crawler/danmaku/9001"
  ```
- **UI**：`/crawlers/bilibili-crawler` 三张卡片接力：「视频完整详情」→「播放直链」/「分P弹幕」。
- **返回解读**：`pages[].cid` 是第二步的入参；合作视频 `is_cooperation=true` 且 `staff[]` 列出各成员分工（owner 只是投稿者）；`durl[].url` 直链**有时效 + Referer 校验**（下载 `curl -H "Referer: https://www.bilibili.com/"`）；`accept_quality[]` 是当前可用的清晰度集合；`timelength` 片长（毫秒）；`support_formats[]` 是各清晰度明细（format/codecs，DASH 场景 durl 为空时靠它选流）；`durl` 段数 >1 表示整片被切分需按序拼接。
- **常见错误**：qn=116/112/80 等高清晰度无 SESSDATA 时上游会降档或 CDN 403 → 带 sessdata；`fnval=4048` 时 `dash=true` 且无 durl（DASH 音视频分离，需自行合流）；aid/cid 不匹配 → 上游非 0 code → 502。

### 3.8 批量收藏一条龙（枚举 → 加收藏）

- **场景**：把一份 av 号清单批量加入某个自建收藏夹（写操作，需 SESSDATA + bili_jct）。
- **端点**：`GET /api/bilibili-tools/favorites`（核对目标夹）→ `POST /api/bilibili-tools/favorites/add`
- **curl**：
  ```bash
  # 第一步：确认目标收藏夹 fid 可写（自建夹 list 接口或网页核对）
  curl -G "http://127.0.0.1:8080/api/bilibili-tools/favorites" \
    --data-urlencode "link=https://space.bilibili.com/42/favlist?fid=12345"

  # 第二步：批量添加（服务端已带节流 + -503/-509 限流退避 + 部分结果保留）
  curl -X POST "http://127.0.0.1:8080/api/bilibili-tools/favorites/add" \
    -H "Content-Type: application/json" \
    -d '{"sessdata":"...","bili_jct":"...","fid":"12345","aids":["170001","2","3"]}'
  ```
- **返回解读**：`results[]` 逐条 `{aid, code, ok, pattern, message}`；聚合看 `ok_count`。`pattern`：0=成功/已收藏（11007/11201）、1=稿件不存在（10003/-404）、2=限流（-503/-509，服务端已自动退避重试）、-1=凭证或未知问题（-111 csrf / -101 未登录 / 网络错误）。
- **常见错误**：`-111` → bili_jct 过期；`-101` → SESSDATA 过期；单批 ≤100 条，超大批次请分批调用。生产环境务必置于鉴权层后。

### 3.9 WBI 签名调试

- **场景**：自行请求其他需要 WBI 签名的 B 站接口时，先在本服务拿 `w_rid`/`wts` 与签名后参数。
- **端点**：`POST /api/bilibili-crawler/wbi/sign`
- **curl**：
  ```bash
  curl -X POST "http://127.0.0.1:8080/api/bilibili-crawler/wbi/sign" \
    -H "Content-Type: application/json" \
    -d '{"params": {"oid": 123, "type": 1, "ps": 20}}'
  # → {"w_rid":"<32位hex>","wts":1710000000,
  #    "signed_params":{...,"w_ts":...,"w_rid":"..."},"query":"oid=123&ps=20&...&w_rid=..."}
  ```
- **返回解读**：`query` 可直接拼到目标接口 URL 后；`signed_params` 是服务端实际发送的形态（参数值字符串化，与上游脚本 str(v) 行为一致）。WBI key 服务端同 client 实例内缓存 1 小时，遇风控（412/-352/-403/-412）自动失效换 key 重试一次。
- **常见错误**：`w_rid` 校验不过多为参数被二次编码——直接用 `query` 原样拼接，不要再 urlencode。

---

## 4. 前端 API Explorer 对应关系

- `/crawlers/<name>` 每页 = `src/modules/crawlers/specs/<name>.js` 里的端点 spec 表驱动
- 表单字段与各模块 `schemas.py` 一一对应；前端不做业务校验（422 错误回显由后端包办）
- 每张卡片右上区域有 `<details>` 折叠的 curl 预览，随输入实时更新，可直接复制
- 响应区：成功 → 可折叠 JSON；失败 → 红 banner（detail / msg / trace_id）

---

## 5. 部署侧注意事项

- `/favorites/add` 写操作置于鉴权层后（JWT / API key / 仅监听 127.0.0.1）
- SESSDATA / bili_jct 由调用方每次请求自带：**不落盘、不进日志**
- `mediacrawler` 仅包装 bilibili 搜索；xhs/douyin 等 6 平台需独立登录会话服务，不进本后端
- `skill_seekers` 串行抓取 + rate_limit，勿当全站镜像工具用
