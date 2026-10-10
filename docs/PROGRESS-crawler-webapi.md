# 爬虫项目 WebAPI 化 — 进度文件

> Ralph 循环任务（nx-rp loop-1，5 轮上限）。每轮开始先读本文件 + `git log` 恢复上下文。

## 状态：第 2 轮完成 ✅（第 1 轮：4 模块交付，见 git d081ad0）

### 第 2 轮改动（改进轮，全部来自第 1 轮遗留清单）

1. ✅ **bilibili_tools 收藏夹 → v3 接口**：`/x/v3/fav/resource/list`（原 /x/space/fav/arc
   ps=1 逐页 → ps≤20 分页按 has_more 停止，请求数 ~20x 减少）；media_id 用完整 mlid
   （fid×100+mid 尾号，依据 bilibili-API-collect/docs/fav/list.md）；响应补 bvid/fav_title；
   state 语义改为 medias[].attr bit0（1=失效）；-403 权限不足也映射 403
2. ✅ **skill_seekers 补 llms.txt 发现层**（原三层引擎 Layer 2）：sitemap 无结果才探测
   `domain/llms.txt`（优先级对齐原仓库），提取 markdown 链接并入 BFS；响应加
   `discovered_via_llms_txt`；偏差已记录（原仓库 llms.txt 命中后跳过整个 HTML 爬取）
3. ✅ **backend/README.md**：原本是空文件，补齐本地运行说明（PYTHONPATH=src）、
   测试分层、全模块索引（含 4 个新爬虫模块）

验收自查（本轮重验）：全量 **251 passed / 5 failed**（5 个为既有基线失败）；
uvicorn 冒烟 /health + /api/mediacrawler/platforms 实测 200；
loop 轮次计数正常（+1/轮，nx-rp 对双层 hook 内部去重，无需摘层）。

### 任务验收标准总状态（1-6 全部满足，见第 1 轮核对）

## 交付物

- 模块：`backend/src/rt_backend/{bilibili_crawler,bilibili_tools,skill_seekers,mediacrawler}/`
- 测试：`backend/tests/{unit,router,e2e}/`（unit 17 + router 28 + e2e 8 = 53 新用例）
- 文档：总文档 + 本文件 + 4 模块 README + backend/README + tests/README
- 决策：scrapy / bilibili-API-collect 不建模块（理由在总文档）

## 后续轮次可选改进（非阻塞，按价值排序）

- [ ] 既有 5 个失败修复（anime×2 是 mock 问题、video_island×3 是 PyAV fixture，均超迁移范围）
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
