# rt-backend

FastAPI 后端（src layout，uv 管理）。架构与扩展规范见
`../.claude/skills/rt-backend-extension/SKILL.md`；部署（Docker + nginx）见仓库根
`Dockerfile` / `nginx.conf` / `supervisord.conf`。

## 本地运行

```bash
# 开发（注意：包未 editable 安装进 venv，uvicorn 直跑需要 PYTHONPATH=src）
cd backend
PYTHONPATH=src uv run uvicorn rt_backend.main:app --reload --port 8080

# 或从仓库根一次拉起前后端（vite 在 81，后端在 8080）
pnpm dev:all
```

容器内不需要手动设置——`Dockerfile` 已有 `ENV PYTHONPATH=/app/backend/src`。

## 测试

```bash
uv run pytest -q                     # 全量
uv run pytest tests/unit -q          # 纯函数层（最快）
uv run pytest tests/router -q        # 模块路由层（respx 拦上游）
uv run pytest tests/e2e -q           # 真实 app 端到端（本地 fixture 站点）
```

分层约定见 `tests/README.md`。全量测试 256 passed / 0 failed（2026-10-10 第 3 轮修复：
anime 两个用例改为动态当前季——原写死 SUMMER 2026 的降级用例随季节轮转失效；
video_island 三个用例的合成 MP4 改用 `tempfile.gettempdir()`——PyAV 原生库不识别
POSIX `/tmp`）。

## 模块索引

| 模块 | 前缀 | 说明 |
|---|---|---|
| `tts/` | `/api/tts` | Edge TTS（流式/时间戳/voices） |
| `sicau_timetable/`、`sicau_timetable_v2/` | `/api/sicau` | SICAU 教务课表（v2 走 Playwright） |
| `bilibili_history/` | `/api/bilibili` | B 站观看历史 |
| `island_cut/` | `/api/island-cut` | 图片/视频岛屿切割（含 video_* 子模块） |
| `reversing/` | `/api/reversing` | F12 逆向挑战 |
| `anime_season/` | `/api/anime` | 番剧季度 |
| `tetris_ai/` | `/api/tetris-ai` | 俄罗斯方块 AI |
| `bilibili_crawler/` | `/api/bilibili-crawler` | B 站爬虫（WBI 签名/评论/UP 动态），迁移自 Bilibili_crawler |
| `bilibili_tools/` | `/api/bilibili-tools` | 收藏夹/批量收藏/音频区，迁移自 BilibiliTools |
| `skill_seekers/` | `/api/skill-seekers` | 文档站 BFS 爬取，迁移自 Skill_Seekers |
| `mediacrawler/` | `/api/mediacrawler` | B 站搜索免登录核心，迁移自 MediaCrawler |

爬虫迁移的范围决策（含未迁移仓库的理由）见 `../docs/crawler-webapi-migration.md`。
