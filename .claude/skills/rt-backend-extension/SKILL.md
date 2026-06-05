---
name: rt-backend-extension
description: 当用户要在 rt 项目中扩展 FastAPI 后端（加新功能模块、新接口、共享资源、新配置项）或修改 Nginx 配置（反代、CORS、HTTPS、WebSocket、限流）时触发此 skill。仅适用于 D:\code\a_js\proj\rt 的 rt_backend + Docker + nginx 架构。
---

# rt 后端扩展 + Nginx 使用指南

适用项目：`D:\code\a_js\proj\rt`（FastAPI + React + Docker + nginx 单容器部署）

---

## 触发场景

- "给后端加个新接口 / 新模块"
- "在 SICAU 模块里再加个学期列表接口"
- "改 nginx 配置，加 HTTPS / 限流 / WebSocket"
- "前后端联调时 nginx 怎么代理后端"
- "容器内 nginx 出问题怎么看日志"

---

## 一、扩展后端的 5 种方式

### 1. 添加新功能模块（最常用）

按 feature 目录组织，复用已有模式：

```
backend/src/rt_backend/
├── core/             # 基础设施（config / logging / http）
├── tts/              # 参考样例
├── sicau_timetable/  # 参考样例
└── <new_feature>/    # 新模块
    ├── __init__.py
    ├── schemas.py    # Pydantic 请求/响应
    ├── service.py    # 业务逻辑
    └── router.py     # APIRouter
```

**接入步骤（3 步）**：

1. 建目录 + 三文件（schemas / service / router）
2. 在 `backend/src/rt_backend/main.py` 挂载：
   ```python
   from .<feature>.router import build_router as _build_<feature>
   app.include_router(_build_<feature>(_http_dep, settings))
   ```
3. 在 `backend/tests/test_<feature>_*.py` 写测试

### 2. 添加新依赖

```bash
cd backend
uv add <package>          # 运行时依赖
uv add --dev <package>    # 仅开发/测试
```

`uv` 自动更新 `pyproject.toml` 和 `uv.lock`。

### 3. 共享资源（HTTP 客户端、缓存、连接池）

在 `lifespan` 中初始化，挂到 `app.state`：

```python
# main.py
http_holder = HttpClientHolder(timeout=30.0)
await http_holder.start()
app.state.http = http_holder
```

新 router 依赖中读取：
```python
def _http_dep(request: Request) -> HttpClientHolder:
    return request.app.state.http
```

### 4. 添加新配置项

在 `core/config.py` 的 `Settings` 加字段：

```python
class Settings(BaseSettings):
    my_feature_api_key: str = ""
    my_feature_timeout: int = 10
```

通过环境变量或 `.env` 注入：
```bash
MY_FEATURE_API_KEY=xxx
```

### 5. 常用添加模式速查

| 需求 | 做法 |
|------|------|
| 新的 REST 端点 | 新 feature 目录，参考 `tts/router.py` |
| 后台任务/调度 | `lifespan` 中 `asyncio.create_task(...)` |
| WebSocket | `@router.websocket("/ws")` |
| 静态文件 | `app.mount("/static", StaticFiles(...))` |
| 中间件 | `app.add_middleware(...)` 在 `create_app` |
| 鉴权 | 写一个 Depends，全局挂载 |

---

## 二、Nginx 使用方式

### 当前架构（容器内）

```
外网 :80 → nginx :80 → {
  /              → /usr/share/nginx/html  (React 静态资源)
  /api/*         → 127.0.0.1:8000         (uvicorn)
}
supervisord 同时拉起 nginx + uvicorn
```

### 1. nginx.conf 关键配置

容器内路径：`/etc/nginx/nginx.conf`

```nginx
events { worker_connections 1024; }

http {
  upstream backend {
    server 127.0.0.1:8000;
  }

  server {
    listen 80;
    
    # 前端 SPA
    location / {
      root /usr/share/nginx/html;
      try_files $uri $uri/ /index.html;   # SPA fallback
    }
    
    # 后端 API 反代
    location /api/ {
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_read_timeout 60s;
    }
    
    location /health {
      proxy_pass http://backend/health;
    }
  }
}
```

### 2. supervisord.conf 关键配置

```ini
[program:nginx]
command=nginx -g "daemon off;"
autorestart=true
stdout_logfile=/var/log/nginx.out.log
stderr_logfile=/var/log/nginx.err.log

[program:backend]
command=uv run uvicorn rt_backend.main:app --host 127.0.0.1 --port 8000
directory=/app/backend
autorestart=true
stdout_logfile=/var/log/backend.out.log
stderr_logfile=/var/log/backend.err.log
```

### 3. 常见 nginx 修改场景

| 需求 | 改法 |
|------|------|
| 加 SSL/HTTPS | `listen 443 ssl;` + 证书路径 |
| 限流 | `limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;` + `limit_req zone=api burst=20;` |
| CORS（前端直连后端时） | `add_header Access-Control-Allow-Origin *;` |
| 大文件上传 | `client_max_body_size 50m;` |
| WebSocket | `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";` |
| 跨域携带 cookie | `proxy_pass_header Set-Cookie;` |
| 静态缓存 | `expires 30d; add_header Cache-Control public;` |
| 隐藏 server 版本 | `server_tokens off;` |

### 4. 本地调试

```bash
# 单独跑后端（不走 nginx）
cd backend
uv run uvicorn rt_backend.main:app --reload --port 8000

# 单独测 nginx
docker run -p 80:80 -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine
```

### 5. 容器内日志

```bash
docker exec -it rt_app tail -f /var/log/nginx.err.log
docker exec -it rt_app tail -f /var/log/backend.out.log
docker exec -it rt_app tail -f /var/log/backend.err.log
```

---

## 三、扩展实战示例

**场景**：在 SICAU 模块加 `GET /api/sicau/semesters` 返回可选学期列表。

1. **加 schema**（`backend/src/rt_backend/sicau_timetable/schemas.py`）：
   ```python
   class SemestersResponse(BaseModel):
       semesters: list[str]
   ```

2. **加 service**（`service.py`）：
   ```python
   async def fetch_semesters(http: HttpClientHolder, user_id: str, password: str) -> list[str]:
       # 登录 + 解析下拉框
       return ["2024-2025-1", "2024-2025-2", "2025-2026-1"]
   ```

3. **加 router**（`router.py`）：
   ```python
   @router.get("/semesters", response_model=SemestersResponse)
   async def semesters(req: ..., http: HttpClientHolder = Depends(http_provider)):
       return {"semesters": await fetch_semesters(http, req.user_id, req.password)}
   ```

4. **写测试** → `uv run pytest -v`

5. **本地验证** → `uv run uvicorn rt_backend.main:app --port 8000`，curl 测一下

6. **CI 部署** → `git push` 即触发 GitHub Actions

---

## 四、避坑（来自实际部署经验）

| 坑 | 症状 | 解决 |
|----|------|------|
| Docker 容器内 `ModuleNotFoundError: rt_backend` | src layout 没设 PYTHONPATH | `Dockerfile` 加 `ENV PYTHONPATH=/app/backend/src` |
| nginx 504 | 后端慢，proxy 超时 | `proxy_read_timeout 60s;` |
| 静态资源 404 刷新 | SPA 路由找不到 | `try_files $uri $uri/ /index.html;` |
| `uv sync` 在容器里装太慢 | 网络问题 | 用 `uv sync --no-dev --frozen` |
| CORS preflight 失败 | 浏览器拦 OPTIONS | nginx 加 `if ($request_method = OPTIONS) { return 204; }` 或 FastAPI 配 CORSMiddleware |
| 接口路径变 `/api/...` 后老客户端 404 | 部署路径迁移 | CI 部署脚本和前端 URL 同步改 |

---

## 错误案例记录

| 错误操作 | 实际后果 | 正确做法 |
|---------|---------|---------|
| 把新功能直接写进 `main.py` | 单文件膨胀，无法测试 | 走 feature 目录 + `build_router` 工厂 |
| 用 `requests` 同步库写异步路由 | 阻塞事件循环 | 全栈用 `httpx.AsyncClient` |
| 缓存路径硬编码 `./tts_cache.db` | 容器重启数据丢 | 通过 `Settings` 注入，可挂卷 |
| nginx 改了没 reload | 旧配置生效 | `docker exec rt_app nginx -s reload` 或重启容器 |
| description 写成内容总结 | skill 不会被触发 | description 必须是触发场景描述 |
