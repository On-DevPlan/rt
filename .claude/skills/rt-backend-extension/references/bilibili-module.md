# B 站历史记录模块 — `bilibili_history/`

> 主 SKILL.md 索引：[[../SKILL.md]]
> 何时读这份 ref：用户要扩展或调试 B 站相关 API（历史记录、tag 统计、收藏夹、登录态）时。

---

## 路由速查

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/bilibili/history/recent` | POST | 最近 N 天的观看记录 |

## 入参/出参

### 入参（`HistoryRequest`）

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `sessdata` | string | ✅ | — | B 站登录 cookie 中的 `SESSDATA` 值（**URL 编码后的原值**） |
| `extra_cookies` | string | ❌ | `null` | 其他 B 站 cookie，例如 `buvid3=xxx; bili_jct=yyy; DedeUserID=zzz` |
| `days` | int | ❌ | `7` | 取最近几天记录。范围 `[1, 90]` |
| `business` | string | ❌ | `"all"` | 业务类型筛选：`all` / `archive` / `live` / `article` |
| `max_pages` | int | ❌ | `10` | 最多翻多少页（单页 30 条）。范围 `[1, 30]` |

### 出参（`HistoryResponse`）

```json
{
  "sessdata_masked": "abc1***ple",
  "days": 7,
  "business": "all",
  "since_ts": 1782791506,
  "since_iso": "2026-06-30T03:51:46Z",
  "until_ts": 1783396306,
  "until_iso": "2026-07-07T03:51:46.827775Z",
  "total": 90,
  "page_count": 3,
  "items": [
    {
      "title": "...",
      "cover": "...",
      "bvid": "BV19XMF6LExn",
      "aid": 116860204883405,
      "cid": 39640959887,
      "author_name": "...",
      "author_mid": 253992474,
      "view_at": 1783395236,
      "view_at_iso": "2026-07-07T03:33:56Z",
      "progress": 245,
      "duration": 654,
      "business": "archive",
      "tag_name": "单机游戏",
      "show_title": null,
      "kid": 116860204883405,
      "dt": 2,
      "is_fav": 0
    }
  ]
}
```

### 错误码

| HTTP | 触发 | 响应 |
|------|------|------|
| 401 | B 站返回 `code = -101`（SESSDATA 无效/过期） | `{"detail": "SESSDATA 无效或已过期（-101）"}` |
| 422 | 请求体参数校验失败 | Pydantic 标准错误 |
| 502 | B 站非 0 code / 非 200 / 网络错误 | `{"detail": "B 站返回错误：..."}` |
| 500 | 未预期错误 | `{"detail": "..."}` |

---

## 关键设计

1. **响应里 SESSDATA 永远脱敏**（`前4***后4`），原始 token 不出现在任何日志/响应里
2. **cursor 翻页 + view_at 截止时间过滤** —— 遇到 `view_at < since_ts` 提前停止
3. **去重** —— `(view_at, bvid/aid, title)` 三元组防止 cursor 边界重复
4. **不需要 WBI 签名** —— 历史接口只要 cookie 鉴权
5. **建议带 `bili_jct` / `DedeUserID` / `buvid3`**，否则 B 站风控可能返回 -352
6. **时区**：所有时间戳都是 **UTC**（Unix 秒），前端按本地时区转换即可

---

## 上游 API

`https://api.bilibili.com/x/web-interface/history/cursor`

URL 参数：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ps` | num | 20 | 每页项数（最大 30） |
| `type` | str | `all` | 分类筛选：all / archive / live / article |
| `max` | num | 0 | 截止目标 id（cursor） |
| `view_at` | num | 0 | 截止时间戳（cursor） |
| `business` | str | 空 | 截止目标业务类型（cursor） |

认证：Cookie (SESSDATA)

---

## 模块结构

```
backend/src/rt_backend/bilibili_history/
├── __init__.py
├── schemas.py    # HistoryRequest / HistoryResponse / HistoryItem
├── service.py    # fetch_recent_history(http, sessdata, ...) + cursor 翻页
└── router.py     # POST /api/bilibili/history/recent
```

挂载位置：`backend/src/rt_backend/main.py:73-74`

```python
from .bilibili_history.router import build_router as _build_bili
app.include_router(_build_bili(_http_dep))
```

路由工厂签名：`build_router(http_provider)` — 只需要 http 时可以省略 settings。

---

## 复用模板（加新 B 站接口时）

如果以后加 `/api/bilibili/tags/stats` 或 `/api/bilibili/favorite/list`：

```python
# 1. schemas.py 加新 Request/Response
# 2. service.py 加 fetch_xxx(http, sessdata, ...)，参数风格一致
# 3. router.py 加新 endpoint，引用同一 http_provider
# 4. main.py 不需要改（router.py 内部 include）
```

---

## 测试

### 单元测试

`backend/tests/test_bilibili_history_router.py` — 4 个测试：

- `test_bilibili_history_success_filters_by_days`：成功 + 按 days 过滤
- `test_bilibili_history_auth_error`：SESSDATA 过期 → 401
- `test_bilibili_history_validation_missing_sessdata`：缺 sessdata → 422
- `test_bilibili_history_validation_days_out_of_range`：days 越界 → 422

用 respx 拦截 httpx 请求，不依赖网络。

### 烟测脚本

`scripts/_bili_smoke.py` — 用真实 cookie 走端到端。

**使用**（重要：SESSDATA 走环境变量，不进 git）：

```powershell
$env:BILI_SESSDATA="你的 SESSDATA"
$env:BILI_EXTRA_COOKIES="buvid3=...; bili_jct=...; DedeUserID=..."
.venv/Scripts/python.exe ../scripts/_bili_smoke.py
```

```bash
export BILI_SESSDATA=xxx
export BILI_EXTRA_COOKIES="..."
uv run python ../scripts/_bili_smoke.py
```

---

## 安全提示

⚠️ **SESSDATA = B 站登录凭证**，泄露 = 账号被盗。

- **不要把这个接口暴露在公网不加鉴权**
- **生产环境务必加一层调用方鉴权**（JWT、API key、或只监听 `127.0.0.1`）
- **后端不会持久化 SESSDATA**——只用于单次 HTTP 请求转给 B 站
- **响应里 `sessdata_masked` 只是脱敏回显**，**不能当 token 用**
- **开发期** 真实 token 存项目外（`memory/bilibili-sessdata-token.md`），不进 git

---

## 扩展方向

加新 B 站接口时建议的优先级：

1. **tag 统计聚合**（`/api/bilibili/tags/stats`）—— 直接返回 `{tag: {count, total_duration, top_authors}}`，前端不用自己 Counter
2. **收藏夹列表**（`/api/bilibili/favorite/list?fid=xxx`）—— 上游 `https://api.bilibili.com/x/v3/fav/folder/created/list-all`
3. **UP 主投稿列表**（`/api/bilibili/space/videos?mid=xxx`）—— 上游 `https://api.bilibili.com/x/space/wbi/arc/search`（**需要 WBI 签名**）
4. **历史记录清理 / 暂停上报**（写操作，**慎做**）

---

## 关键参考文件

| 路径 | 内容 |
|------|------|
| `backend/src/rt_backend/bilibili_history/service.py` | 翻页 + 过滤 + 脱敏实现 |
| `docs/api-bilibili-history.md` | 完整 API 文档（请求/响应/字段/安全） |
| `.claude/repo/bilibili-API-collect/docs/historytoview/history.md` | 上游 API 详细文档 |
| `.claude/repo/Bilibili_crawler/b站使用wbi签名的爬取方式.py` | WBI 签名算法（加 UP 主投稿等接口时需要） |
