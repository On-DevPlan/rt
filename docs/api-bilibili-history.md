# B 站观看历史 API

> 路径：`POST /api/bilibili/history/recent`
> 模块：`backend/src/rt_backend/bilibili_history/`
> 上游：https://api.bilibili.com/x/web-interface/history/cursor

通过用户的 SESSDATA cookie 获取最近 N 天的观看记录，附带分页/筛选/脱敏等开箱即用的处理。

---

## 1. 请求

### Header

| 字段             | 值                   |
| ---------------- | -------------------- |
| `Content-Type` | `application/json` |

### Body

| 字段              | 类型   | 必填 | 默认      | 说明                                                                                                           |
| ----------------- | ------ | ---- | --------- | -------------------------------------------------------------------------------------------------------------- |
| `sessdata`      | string | ✅   | —        | B 站登录 cookie 中的`SESSDATA` 值（**URL 编码后的原值**）                                              |
| `extra_cookies` | string | ❌   | `null`  | 其他 B 站 cookie，例如`buvid3=xxx; bili_jct=yyy; DedeUserID=zzz`。模块会自动去掉 `SESSDATA=xxx` 段防止覆盖 |
| `days`          | int    | ❌   | `7`     | 取最近几天的记录。范围`[1, 90]`                                                                              |
| `business`      | string | ❌   | `"all"` | 业务类型筛选：`all` / `archive` / `live` / `article`                                                   |
| `max_pages`     | int    | ❌   | `10`    | 最多翻多少页（单页 30 条）。范围`[1, 30]`                                                                    |

### 示例

```bash
curl -X POST http://localhost:8000/api/bilibili/history/recent \
  -H "Content-Type: application/json" \
  -d '{
    "sessdata": "abc%2C1234567890%2C1234%2Aexample",
    "extra_cookies": "buvid3=41C80A8B-...; bili_jct=7c3aa1...; DedeUserID=3546381088196737",
    "days": 7,
    "business": "all",
    "max_pages": 5
  }'
```

---

## 2. 响应

### 成功 `200`

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
      "title": "原价180现价只要9块…",
      "cover": "http://i1.hdslb.com/bfs/archive/d1c7a3e44...",
      "bvid": "BV19XMF6LExn",
      "aid": 116860204883405,
      "cid": 39640959887,
      "author_name": "蒸汽居士",
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

### 字段说明

| 字段                         | 说明                                                                                                       |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `sessdata_masked`          | 入参 SESSDATA 的脱敏形式（前 4 +`***` + 后 4），**用于回显**。原始 token 不会出现在响应里          |
| `since_ts` / `since_iso` | 时间窗口起点（UTC）                                                                                        |
| `until_ts` / `until_iso` | 时间窗口终点（UTC）                                                                                        |
| `total`                    | 返回的条目数（已按`view_at >= since_ts` 过滤）                                                           |
| `page_count`               | 实际调用的 B 站分页数（可能小于`max_pages`——遇到截止时间或无更多数据会提前停止）                       |
| `items[].view_at`          | 观看时间（Unix 秒）                                                                                        |
| `items[].view_at_iso`      | 观看时间 ISO8601                                                                                           |
| `items[].bvid`             | 稿件 BV 号（仅`archive`）                                                                                |
| `items[].aid`              | 稿件 avid（仅`archive`）                                                                                 |
| `items[].tag_name`         | 子分区名（**用于 tag 统计**）                                                                        |
| `items[].business`         | `archive` / `pgc` / `live` / `article` / `article-list`                                          |
| `items[].progress`         | 观看进度（秒）                                                                                             |
| `items[].duration`         | 视频总时长（秒）                                                                                           |
| `items[].is_fav`           | `0` = 未收藏 / `1` = 已收藏                                                                            |
| `items[].dt`               | 观看平台代码：`1/3/5/7` 手机端 / `2` web 端 / `4/6` pad / `9` 智能音箱 / `33` TV 端 / `0` 其他 |

---

## 3. 错误码

| HTTP          | 触发条件                                      | 响应示例                                                                                       |
| ------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **401** | B 站返回`code = -101`（SESSDATA 无效/过期） | `{"detail": "SESSDATA 无效或已过期（-101）"}`                                                |
| **422** | 请求体参数校验失败（缺字段、`days` 越界等） | `{"detail": [{"loc": ["body", "days"], "msg": "Input should be less than or equal to 90"}]}` |
| **502** | B 站返回非 0 code / 非 200 状态码 / 网络错误  | `{"detail": "B 站返回错误：code=xxx, message=yyy"}`                                          |
| **500** | 未预期错误                                    | `{"detail": "未预期错误：xxx"}`                                                              |

---

## 4. 实现说明

### 翻页机制

B 站历史接口使用 cursor 链式翻页：

- 入参 `max` / `view_at` / `business` 三个一起充当"下一页指针"
- 模块按 `max_pages` 翻页，**遇到 `view_at < since_ts` 时提前停止**（不会浪费请求）
- 用 `(view_at, bvid/aid, title)` 三元组去重，防止 cursor 边界处的同一条记录被收两次

### SESSDATA 脱敏

- **入参**：原样接收，传入时是 URL 编码的形式
- **出参**：永远以 `sessdata_masked` 返回（前 4 + `***` + 后 4），原始 token 不会出现在响应里
- **模块内部**：用 `httpx` 注入到 `Cookie` header 中传给 B 站，**不会写日志或持久化**

### 为什么不需要 WBI 签名

历史接口只用 cookie 鉴权，**不需要 `wts` / `w_rid`**。但建议同时传 `extra_cookies` 带上 `bili_jct` / `DedeUserID` / `buvid3`，否则 B 站风控可能返回 -352。

### 时区

所有时间戳都是 **UTC**（Unix 秒），前端展示时按本地时区转换即可。`view_at_iso` 用 ISO8601 标准格式带 `Z` 后缀。

---

## 5. 前端调用示例

### React + fetch

```tsx
async function fetchHistory(sessdata: string) {
  const r = await fetch('/api/bilibili/history/recent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessdata,
      extra_cookies: getCookieString(), // 从 document.cookie 拼出非 SESSDATA 段
      days: 7,
      max_pages: 5,
    }),
  });
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

// 简单 tag 聚合
function tagStats(items: HistoryItem[]): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, it) => {
    if (it.tag_name) acc[it.tag_name] = (acc[it.tag_name] ?? 0) + 1;
    return acc;
  }, {});
}
```

### Vue + axios

```js
import axios from 'axios';

export const recentHistory = (sessdata, days = 7) =>
  axios.post('/api/bilibili/history/recent', {
    sessdata,
    days,
    max_pages: 5,
  });
```

---

## 6. 安全提示

⚠️ **SESSDATA = 你的 B 站登录凭证**，泄露等同于账号被盗。

本接口的 token 是**用户自己提供**的（前端从浏览器 cookie 读 → 传给后端 → 后端代为请求 B 站），所以：

1. **不要把这个接口暴露在公网不加鉴权**——任何拿到你服务地址的人只要提供 SESSDATA 就能拉你的历史记录
2. **生产环境务必加一层调用方鉴权**（JWT、API key、或者直接把后端当本地工具用）
3. **后端不会持久化 SESSDATA**——只用于单次 HTTP 请求转给 B 站，不写日志/数据库
4. **响应里的 `sessdata_masked` 只是脱敏回显**，**不是用来当 token 用的**

---

## 7. 本地调试

### 启动服务

```bash
cd backend
PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8000
```

### 烟测脚本

```bash
# PowerShell
$env:BILI_SESSDATA="你的 SESSDATA 值"
$env:BILI_EXTRA_COOKIES="buvid3=xxx; bili_jct=yyy; DedeUserID=zzz"
.venv/Scripts/python.exe ../scripts/_bili_smoke.py

# bash
export BILI_SESSDATA=xxx
export BILI_EXTRA_COOKIES="..."
uv run python ../scripts/_bili_smoke.py
```

### 单元测试

```bash
cd backend
uv run pytest tests/test_bilibili_history_router.py -v
```

### 拿 SESSDATA

1. 浏览器登录 https://www.bilibili.com
2. F12 → Application → Cookies → `https://www.bilibili.com`
3. 复制 `SESSDATA` 的 value（看起来像 `abc,1234567890,...` URL 编码后的长串）

---

## 8. 相关文件

| 文件                                                                | 作用                           |
| ------------------------------------------------------------------- | ------------------------------ |
| `backend/src/rt_backend/bilibili_history/schemas.py`              | Pydantic 模型                  |
| `backend/src/rt_backend/bilibili_history/service.py`              | 翻页 + 过滤 + 脱敏逻辑         |
| `backend/src/rt_backend/bilibili_history/router.py`               | FastAPI 路由                   |
| `backend/src/rt_backend/main.py`                                  | 第 73-74 行挂载路由            |
| `backend/tests/test_bilibili_history_router.py`                   | 单元测试（用 respx 拦截 HTTP） |
| `scripts/_bili_smoke.py`                                          | 真实 cookie 烟测               |
| `.claude/repo/bilibili-API-collect/docs/historytoview/history.md` | 上游 API 文档参考              |
