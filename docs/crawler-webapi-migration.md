# 爬虫项目 WebAPI 化迁移总文档

把 `D:\code\a_js\proj\rt\.claude\repo` 下的爬虫项目迁移进 rt 后端（FastAPI），
**一个仓库一个独立 API 前缀**，便于隔离与区分。规范遵循
`.claude/skills/rt-backend-extension/SKILL.md`（feature 目录 + `build_router` 工厂 + 复用 `core/`，无新增中间件）。

日期：2026-10-10　｜　进度文件：`docs/PROGRESS-crawler-webapi.md`

## 迁移范围决策

`.claude/repo` 全部 12 个仓库逐一判定：

| 仓库 | 判定 | 处理 |
|---|---|---|
| **Bilibili_crawler** | 爬虫（requests 脚本集） | ✅ → `/api/bilibili-crawler` |
| **BilibiliTools** | 爬虫/工具集 | ✅ → `/api/bilibili-tools` |
| **Skill_Seekers** | 爬虫（文档站 BFS） | ✅ → `/api/skill-seekers` |
| **MediaCrawler** | 爬虫（Playwright 多平台，重量级） | ✅ 克制包装 → `/api/mediacrawler`（免登录核心） |
| **scrapy** | 是框架本身，不是爬虫应用 | ❌ 不建模块（理由见下） |
| **bilibili-API-collect** | 纯 API 文档集，无可运行代码 | ❌ 不建模块，作参考资料 |
| gomoku-ai / gomoku-first-move-always-win / tetris_game / tetrisai / cleanlab / daily-slow-english / _self | 非爬虫 | ❌ 不迁移（tetrisai 已有历史模块 `tetris_ai/`） |

### scrapy 跳过理由

1. `.claude/repo/scrapy` 是 **Scrapy 框架的源码**，不含任何具体爬虫应用；"把框架 API 化"
   没有对应的能力迁移物。
2. Scrapy 运行依赖 **Twisted reactor**，与 FastAPI 的 asyncio 事件循环冲突：要么在子进程跑
   （等价于把后端当任务队列，还要处理结果回传/超时/资源），要么 reactor 隔离黑魔法——
   两者都与本项目「单容器、无特殊中间件」的定位相悖。
3. 后端 venv 未安装 scrapy（已验证），vendor 进来要新增 twisted 等一串重依赖，收益为零——
   通用抓取需求已由 `skill_seekers` 模块的 BFS 爬虫覆盖。
4. 如未来确需跑 Scrapy spider，正确做法是独立 worker 服务 + 队列，而不是塞进 rt 后端。

### bilibili-API-collect 处理

纯文档仓库（B 站各业务线 API 的逆向文档），无代码可迁移。本迁移中它是**接口事实的参考来源**
（评论区 type=1 视频 / type=17 动态、WBI 签名语义等），已体现在 `bilibili_crawler` 模块的
实现与文档中。

## 模块索引

| 模块 | 前缀 | 功能 | 代码 | 测试（unit/router/e2e） | 文档 |
|---|---|---|---|---|---|
| `bilibili_crawler` | `/api/bilibili-crawler` | WBI 签名、av↔bv、视频信息、两级评论、UP 动态 | `src/rt_backend/bilibili_crawler/` | 5 / 8 / 2 | `bilibili_crawler/README.md` |
| `bilibili_tools` | `/api/bilibili-tools` | 收藏夹枚举、批量收藏、音频区（歌曲/歌单/UP 歌曲） | `src/rt_backend/bilibili_tools/` | — / 8 / 1 | `bilibili_tools/README.md` |
| `skill_seekers` | `/api/skill-seekers` | 文档站爬取（sitemap 发现 + BFS + 正文提取） | `src/rt_backend/skill_seekers/` | 14 / 5 / 3 | `skill_seekers/README.md` |
| `mediacrawler` | `/api/mediacrawler` | B 站关键词搜索（WBI）、平台能力矩阵 | `src/rt_backend/mediacrawler/` | — / 4 / 2 | `mediacrawler/README.md` |

（e2e 计数含多模块共用用例；`mediacrawler` 的 WBI 签名跨模块复用 `bilibili_crawler.service`。）

共性设计：

- 全部走 `core/http.HttpClientHolder`（共享 httpx.AsyncClient），`build_router(http_dep)` 工厂挂载
- **无新增中间件、无新重依赖**（未用上 playwright/scrapy；skill_seekers 爬虫用 bs4+httpx 精简重写）
- 错误统一映射：上游 `-101` 类 → 401；风控（412/-412）与上游异常 → 502；收藏夹私有 → 403；参数错误 → 422
- 上游凭证（SESSDATA/bili_jct）一律由请求传入、不落盘不进日志

## 启动与验证

```bash
cd D:\code\a_js\proj\rt\backend
uv run uvicorn rt_backend.main:app --port 8080   # http://127.0.0.1:8080/docs 看 OpenAPI
uv run pytest -q                                  # 全量（unit/ + router/ + e2e/ + 既有平铺测试）
```

既有 5 个失败（anime×2、video_island×3）为迁移前就存在的 Windows 环境问题，与本次无关。

## curl 案例速查（完整版见各模块 README）

```bash
B=http://127.0.0.1:8080

# bilibili-crawler：av↔bv / 视频信息 / 两级评论 / WBI 签名
curl "$B/api/bilibili-crawler/convert?aid=170001"            # → BV17x411w7KC
curl "$B/api/bilibili-crawler/video/BV1xx411c7mD"
curl -X POST "$B/api/bilibili-crawler/comments" -H "Content-Type: application/json" \
  -d '{"oid":"170001","pages":2}'
curl -X POST "$B/api/bilibili-crawler/wbi/sign" -H "Content-Type: application/json" \
  -d '{"params":{"oid":1,"type":1}}'

# bilibili-tools：收藏夹 / 批量收藏 / 音频区
curl "$B/api/bilibili-tools/favorites?link=https://space.bilibili.com/42/favlist?fid=12345"
curl -X POST "$B/api/bilibili-tools/favorites/add" -H "Content-Type: application/json" \
  -d '{"sessdata":"...","bili_jct":"...","fid":"123","aids":["170001"]}'
curl "$B/api/bilibili-tools/audio/au241921?quality=2"

# skill-seekers：文档站 BFS 爬取
curl -X POST "$B/api/skill-seekers/scrape" -H "Content-Type: application/json" \
  -d '{"base_url":"https://docs.example.com/guide/","max_pages":10,"dry_run":true}'

# mediacrawler：能力矩阵 / B 站搜索
curl "$B/api/mediacrawler/platforms"
curl -X POST "$B/api/mediacrawler/search" -H "Content-Type: application/json" \
  -d '{"keyword":"python","order":"click"}'
```

## 测试分层（用户要求）

见 `backend/tests/README.md`。要点：`tests/unit`（纯函数）→ `tests/router`（respx 拦上游）
→ `tests/e2e`（真实 `create_app` + 本地 fixture 文档站走真 HTTP 回环）；既有 24 个平铺测试
保持原位。上游接口全部拦截/本地化，**测试不依赖外网与真实 cookie**。

## 已知限制与后续方向

- skill_seekers 不执行 JS：SPA 站点需原仓库 Playwright 渲染层，未迁移
- mediacrawler 仅包装 bilibili 搜索；其余平台需独立登录会话服务，不宜塞进本后端
- 评论/搜索接口对无 cookie 请求有风控概率（412/-412 → 502，提示带 SESSDATA）
- 部署提醒（来自 skill）：后端目前无调用方鉴权，`/favorites/add` 这类**写操作**接口
  部署时应置于鉴权层之后
