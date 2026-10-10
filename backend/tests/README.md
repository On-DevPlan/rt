# tests/ 分层约定

## 目录结构

```
backend/tests/
├── conftest.py            # 顶层共享 fixture（既有：tts client_app）
├── test_*.py              # 既有 24 个测试文件——保持原位，不做迁移（见「决策」）
├── unit/                  # 第 1 层：纯函数单测
├── router/                # 第 2 层：模块路由测试
└── e2e/                   # 第 3 层：真实 app 端到端
    ├── conftest.py        # fixture 文档站 + real_app_client
    └── test_crawler_modules_e2e.py
```

## 各层职责与写法

| 层 | 测什么 | 依赖 | 不允许 |
|---|---|---|---|
| `unit/` | service 纯函数（算法、规范化、解析） | 无 IO；上游用 `httpx.MockTransport` | TestClient、respx、网络 |
| `router/` | 单模块路由：参数校验、错误映射、业务流 | `TestClient` + `respx.mock` 拦上游 | 真实外网、真实 cookie |
| `e2e/` | 真实 `create_app()` 全链路：装配、前缀挂载、跨层行为 | fixture 文档站走**真 HTTP 回环**；上游仍用 respx | 依赖外网稳定 |

要点：

- **unit**：一个用例一个行为；断言「规格」而不是复述实现（例：`get_mixin_key` 断言
  `mixin[i] == orig[TAB[i]]`，不要用同一套 TAB 重算一遍）。
- **router**：`respx.mock(base_url=..., assert_all_called=False)`——截断/过滤/dry-run
  场景天然打不满全部路由，默认的 `assert_all_called=True` 会误报。
- **e2e**：`real_app_client` fixture 用真实 `main.create_app()`（全部路由 + lifespan），
  仅把 `PlaywrightHolder.start`（sicau_v2 的 chromium 急启动）patch 成 no-op；
  爬虫对 `doc_site` fixture（session 级 uvicorn，随机端口）发真 HTTP。

## 运行

```bash
uv run pytest tests/unit -q              # 最快，纯逻辑
uv run pytest tests/router -q            # 单模块调试
uv run pytest tests/e2e -q               # 提交前全链路
uv run pytest -q                         # 全量（含既有平铺测试）
```

## 决策记录

1. **既有 24 个测试文件不迁移**：`pytest.ini` 的 `testpaths=["tests"]` 对子目录自动生效，
   平铺与分层并存；迁老文件是无功能收益的 churn，且会污染本次迁移的 diff。
   新模块测试一律进对应层。
2. **fixture 站点而非 respx 全拦**：爬虫的「端到端」价值在于真实 HTTP 栈（URL 拼接、
   绝对化、去重），respx 拦不到传输层细节，故 e2e 用本地 uvicorn 起真站。
3. **命名**：`test_<module>_service.py`（unit）/ `test_<module>_router.py`（router）/
   `test_<topic>_e2e.py`（e2e）。
