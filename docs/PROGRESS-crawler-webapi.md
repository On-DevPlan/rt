# 爬虫项目 WebAPI 化 — 进度文件

> Ralph 循环任务（nx-rp loop-1，5 轮上限）。每轮开始先读本文件 + `git log` 恢复上下文。

## 状态：第 1 轮全部 7 个任务完成 ✅

验收标准逐项核对：

1. ✅ 4 个模块目录 + 独立前缀，main.py 已挂载（OpenAPI 实测 13 个新端点）
2. ✅ `uv run pytest -q`：**245 passed / 5 failed**（5 个为迁移前既有失败：anime×2、video_island×3，与本次无关）；新增 unit/13+router/25+e2e/8 共 46 用例全绿
3. ✅ `PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8099` 实测启动：/health ok、convert 真实 HTTP 正确返回（注意：src layout 未 editable 安装，本地跑要 PYTHONPATH=src，Docker 已有 ENV）
4. ✅ 每模块 README：功能/路由表/curl 案例（4 份）
5. ✅ 总文档 `docs/crawler-webapi-migration.md`（范围决策含 scrapy 跳过理由、API-collect 参考记录）
6. ✅ 本文件每轮更新

## 交付物

- 模块：`backend/src/rt_backend/{bilibili_crawler,bilibili_tools,skill_seekers,mediacrawler}/`
- 测试：`backend/tests/{unit,router,e2e}/` + `backend/tests/README.md`（分层约定）
- 文档：`docs/crawler-webapi-migration.md`（总）、`docs/PROGRESS-crawler-webapi.md`（本文件）
- 决策：scrapy（框架非应用 + Twisted/asyncio 冲突）与 bilibili-API-collect（纯文档）不建模块，理由在总文档

## 后续轮次可选改进（非阻塞）

- [ ] 既有 5 个失败修复（超本次范围，需 PyAV fixture / anime mock 调查）
- [ ] bilibili_tools 收藏夹枚举换新接口 `/x/v3/fav/resource/list`（现为原脚本 ps=1 逐页，慢）
- [ ] skill_seekers 的 llms.txt 发现层（原仓库 Layer 2）补齐
- [ ] mediacrawler 其余平台 → 独立登录会话服务（不在本后端做）
- [ ] 写操作端点（/favorites/add）部署时的调用方鉴权（skill 文档提醒）
- [ ] rt_backend editable 安装进 venv 或加 PYTHONPATH 说明到 backend/README

## 已踩坑记录（保留，后续轮次避免重踩）

1. `is_valid_url` 必须取 base_url 的**目录部分**做前缀（index.html → 所在目录）
2. `enc_wbi` 参数值 `str(v)` 字符串化（原脚本行为），断言注意
3. respx 默认 `assert_all_called=True`：截断/过滤/dry-run 场景传 `assert_all_called=False`
4. mock 的 wbi img/sub key 必须 32 字符（混淆表索引最大 63）
5. FastAPI 按注册顺序匹配路由：通配 `/audio/{sid}` 注册在具体路由之后
6. `%2F` 路径参数匹配不可靠：带斜杠链接走 query 参数
7. `extract_content` 跳过 <20 字符段落：fixture 正文必须写长句
8. git-bash cwd 跨命令漂移：所有命令显式 `cd` 绝对路径
