# 爬虫项目 WebAPI 化 — 进度文件

> Ralph 循环任务（nx-rp loop-1，5 轮上限）。每轮开始先读本文件 + `git log` 恢复上下文。

## 状态：第 4 轮完成 ✅（终验轮：全部验收项从干净状态重验通过）

### 轮次历史

- **第 1 轮（d081ad0）**：4 模块交付 + 分层测试（unit/router/e2e）+ 全套文档
- **第 2 轮（deee0d8）**：收藏夹 v3 接口 + skill_seekers llms.txt Layer 2 + backend/README
- **第 3 轮（b215a1c）**：修复 5 个既有基线失败（纯测试修复，零生产代码改动）
- **第 4 轮（本轮）**：终验 + ASGITransport 字面合规用例

### 第 4 轮改动

- 新增 `test_real_app_via_httpx_asgi_transport`：验收标准 2 写明「httpx ASGITransport
  启动真实 ASGI app」——原 e2e 用 TestClient（语义等价但非字面）。新用例用原生
  `httpx.AsyncClient + ASGITransport` 手动驱动 lifespan，对 fixture 站点跑完整爬取链路

### 第 4 轮终验结果（全部从当前 HEAD 重验）

1. ✅ 4 模块 + 独立前缀挂载（OpenAPI 13 端点）
2. ✅ `uv run pytest -q`：**257 passed / 0 failed**（含 ASGITransport 字面用例）
3. ✅ `PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8080`：
   /health + /docs + /api/mediacrawler/platforms 实测 200（验收原文端口 8080）
4. ✅ 4 模块 README 齐备（功能/路由表/curl 案例）
5. ✅ 总文档含 scrapy / bilibili-API-collect 决策理由 + 模块索引 + curl 汇总
6. ✅ 本文件每轮更新
- ✅ 「不引入特殊中间件」复核：`git diff d081ad0^..HEAD -- main.py` 只含 router 挂载与 import

### 第 3 轮改动明细（历史，见 b215a1c）

1. **anime×2（时间炸弹）**：降级只在查「当前季」时启用（service 的 `degraded_ok`），
   两个降级用例写死 SUMMER 2026——写测试时是当前季，10 月起 FALL 接管，降级路径不再
   触发。改为 `current_season_now()` 动态取当前季 + 动态 yuc URL（月份映射 1/4/7/10）
2. **video_island×3（Windows 环境炸弹）**：合成 MP4 写死 `/tmp/...`——PyAV 是原生库
   不走 MSYS 路径翻译，Windows 上必挂。改 `tempfile.gettempdir()`

### 验收自查（第 3 轮逐项）

1. ✅ 4 模块 + 独立前缀，main.py 挂载（OpenAPI 13 端点）
2. ✅ `uv run pytest -q`：256 passed / 0 failed（第 4 轮终验更新为 257/0）；e2e 走真实 ASGI app
   + 本地 fixture 站点真 HTTP，上游 respx 拦截，零外网零真实 cookie 依赖）
3. ✅ `PYTHONPATH=src uv run uvicorn rt_backend.main:app` 冒烟：/health + convert 实测正确
4. ✅ 4 模块 README（功能/路由表/curl 案例）齐全
5. ✅ 总文档（范围决策/模块索引/启动方式/curl 汇总）
6. ✅ 本文件每轮更新

## 交付物

- 模块：`backend/src/rt_backend/{bilibili_crawler,bilibili_tools,skill_seekers,mediacrawler}/`
- 测试：`backend/tests/{unit,router,e2e}/`（unit 17 + router 28 + e2e 8 = 53 新用例）
- 文档：总文档 + 本文件 + 4 模块 README + backend/README + tests/README
- 决策：scrapy / bilibili-API-collect 不建模块（理由在总文档）

## 剩余可选项（全部非阻塞，价值递减）

- [ ] skill_seekers 可选返回 llms.txt 原文内容（对齐原仓库「跳过 HTML 爬取」语义）
- [ ] mediacrawler 其余平台 → 独立登录会话服务（不在本后端做）
- [ ] 写操作端点（/favorites/add）部署时的调用方鉴权（skill 文档提醒）
- [ ] uv build-system 化让 uv run 自动装包（有 Docker 构建风险，需先验证 docker build）

## 已踩坑记录（保留，后续轮次避免重踩）

1. `is_valid_url` 必须取 base_url 的**目录部分**做前缀（index.html → 所在目录）
2. `enc_wbi` 参数值 `str(v)` 字符串化（原脚本行为），断言注意
3. respx 默认 `assert_all_called=True`：截断/过滤/dry-run 场景传 `assert_all_called=False`
4. mock 的 wbi img/sub key 必须 32 字符（混淆表索引最大 63）
5. FastAPI 按注册顺序匹配路由：通配 `/audio/{sid}` 注册在具体路由之后
6. `%2F` 路径参数匹配不可靠：带斜杠链接走 query 参数
7. `extract_content` 跳过 <20 字符段落：fixture 正文必须写长句
8. git-bash cwd 跨命令漂移：所有命令显式 `cd` 绝对路径
9. markdown 链接正则要允许可选 `"title"` 部分：`\((url)(?:\s+"[^"]*")?\)`
10. v3 收藏夹接口的 media_id 是完整 mlid（fid×100+mid 尾号），不是原始 fid
11. 时间相关测试禁止写死季节/年份：降级路径随 `degraded_ok` 依赖当前季，用
    `current_season_now()` 动态取
12. PyAV（原生库）路径必须用平台临时目录，POSIX `/tmp` 在 Windows 不被识别
