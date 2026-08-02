# 五子棋引擎替换：Rapfi 接入设计

> 日期：2026-08-02
> 状态：已通过 brainstorming，待用户复核后进入 writing-plans

## 1. 背景与目标

`rt` 项目的五子棋模块当前后端引擎（`backend/src/rt_backend/gomoku_ai/service.py`）是手写的
**棋型评分 + 1 步前瞻（beam 6/12）**，强度很低（"智能判断非常落后"）。

目标：把落子引擎替换为 **Rapfi**（[`dhbloo/rapfi`](https://github.com/dhbloo/rapfi)）——
GomoCup 2024 冠军、Botzone 排名第一的 Gomoku/Renju 引擎；纯 CPU、AVX2、开源。

替换后，对外 API `POST /api/gomoku/next-move` 的**契约保持不变**，前端零改动；
Rapfi 不可用时静默回退旧 Python 引擎，永不向客户端抛 500。

## 2. 关键事实（已核实）

- Rapfi 实现完整 Gomocup/piskvork 文本协议，含 `START` / `BEGIN` / `TURN` / `BOARD … DONE` / `INFO …` / `END` / `RESTART`。
- 现代版 Rapfi 是 **NN（蒸馏网络）评估**，二进制需配套**训练好的模型文件**（模型不在源码里，随 release 分发）。参见 [arXiv:2503.13178](https://arxiv.org/html/2503.13178v1)。
- 构建：CMake，README 提供 `x64-clang-AVX2`（或 MSVC AVX2）预设。
- 参考实现（同类 HTTP 包装）：[`XingHehy/gomoku-rapfi`](https://github.com/XingHehy/gomoku-rapfi)。

## 3. 方案选型

**采用：每请求一个子进程，走 Gomocup `BOARD` 协议。**

每请求：spawn `pbrain-Rapfi` → `START 15` → 设 `INFO`（思考时间/内存/线程/节点上限）→
`BOARD … DONE` → 读落子行 → `END` → kill。用 `asyncio.create_subprocess_exec` 驱动，带硬超时。

- 真**无状态**，与现有 API 契约完全一致；无共享状态/并发 bug；易测试。
- 代价：每步 ~100–200ms 进程启动 + 模型加载开销，相对思考时间（0.5–5s）可忽略。
- 否决方案：常驻进程池（复杂、难测、单机自用 overkill）；守护进程/FFI（Rapfi 非为库设计，复杂度过高）。

## 4. 决策记录

| 决策 | 结论 |
|---|---|
| 强度档位 | Rapfi 全包，靠思考时间 `time_turn` 控档；1=弱/2=中/3=强 |
| 思考时间 | 平衡型：弱 0.5s / 中 2.0s / 强 5.0s |
| 旧 Python 引擎 | 保留，**仅作回退**（AVX2 缺失 / Rapfi 崩溃 / 熔断时启用），不暴露给前端选择 |
| 进程模型 | 每请求一子进程（方案 A） |
| 部署 | Docker 多阶段**从源码编译** Rapfi AVX2 + 从 release 取模型（可复现、保证 ISA） |
| 对外 API | 零改动；新增可选响应字段 `engine` 标注实际所用引擎 |

## 5. 架构与数据流

```
前端（不变）  gomokuApi.fetchNextMove()
   │  POST /api/gomoku/next-move {board, to_move, top_k, strength}
   ▼
router.next_move()
   │  1. 校验 board / to_move / strength（沿用现有校验）
   │  2. strength → time_turn（0.5 / 2.0 / 5.0s）
   │  3. 空棋盘 → 直接返回天元（fast path，不调 Rapfi）
   │  4. is_rapfi_available() 且未熔断 → await rapfi.compute_move(...)
   │     失败（超时/崩溃/解析失败）→ 静默回退 service.best_move(...)
   ▼
rapfi.compute_move()（新文件 gomoku_ai/rapfi.py）
   │  asyncio 子进程 + BOARD 协议往返 → 解析 "x,y"
   ▼
NextMoveResponse（字段语义见 §7）
```

## 6. 后端模块设计

### 6.1 新文件 `gomoku_ai/rapfi.py`（纯函数，无 FastAPI/Pydantic，沿用 board.py 风格）

**常量与配置（读自 `Settings`，可被环境变量覆盖）：**
- `RAPFI_BIN`：`/opt/rapfi/pbrain-Rapfi`
- `RAPFI_MODEL_DIR`：模型文件所在目录（Rapfi 以 CWD 或该目录解析模型）
- `TIME_TURN_BY_STRENGTH = {1: 500, 2: 2000, 3: 5000}`（毫秒）
- `MAX_MEMORY_MB = 256`、`THREADS = 1`、`MAX_NODE = 10_000_000`

**类型：**
```python
@dataclass(frozen=True)
class RapfiMove:
    row: int
    col: int
    score: int            # 解析自 INFO score；拿不到为 0
    winning: bool         # 本地 board.py 计算
    blocks: bool          # 本地 board.py 计算
```
异常：`class RapfiUnavailable(Exception)`。

**函数：**
- `_has_avx2() -> bool`：读 `/proc/cpuinfo` 是否含 `avx2` flag（Linux 容器）；结果缓存。
- `is_rapfi_available() -> bool`：① 二进制存在（`os.path.exists` + 可执行）② `_has_avx2()` ③ 未触发熔断。启动时与每请求前调用，结果缓存。
- `async def compute_move(board, to_move, time_turn_ms, timeout_s) -> RapfiMove`：
  1. `asyncio.create_subprocess_exec(RAPFI_BIN, cwd=RAPFI_MODEL_DIR, stdin/stdout=PIPE, stderr=PIPE)`。
  2. 写入并按行读应答：
     - `START 15\n` → 期望 `OK`（容许 `UNKNOWN command`，非致命）。
     - `INFO time_turn {time_turn_ms}\n`
     - `INFO max_memory {MAX_MEMORY_MB}\n`
     - `INFO number_of_threads {THREADS}\n`
     - `INFO max_node {MAX_NODE}\n`
     - 构造 `BOARD\n` + 每个非空格 `<col>,<row>,<color>\n`（颜色：`to_move`→`1`，对方→`2`）+ `DONE\n`。
     - 读 stdout，**过滤掉** `INFO` / `MESSAGE` / `DEBUG` / `ERROR` / `UNKNOWN` 行，取第一个形如 `"<int>,<int>"` 的行作为落子。
     - 解析 `x,y`（Gomocup：x=col, y=row, 0 基）→ `(row=y, col=x)`。
  3. `END\n`；`await asyncio.wait_for(proc.wait(), timeout=2)`；超时则 `proc.kill()`。
  4. 捕获任何异常（超时、非零退出、解析失败）→ 抛 `RapfiUnavailable`。
- **熔断**：模块级计数器，连续 `N=3` 次 `RapfiUnavailable` → 置 `_disabled=True`，后续 `is_rapfi_available()` 直接返回 `False`；记录 warning。进程内熔断（重启恢复）。

### 6.2 坐标与颜色映射（关键正确性）

- Rapfi/Gomocup 坐标：输出 `"x,y"` 中 `x=列(col)`、`y=行(row)`、0 基、原点左上。
- 我们 `board[row][col]`：`row=0` 顶部、`col=0` 左侧。映射：引擎 `(x,y)` ↔ `(col=x, row=y)`，1:1 无翻转。
- BOARD 颜色：把"本步要走的方"`to_move` 编为 `1`，对方编为 `2`。引擎在 BOARD/DONE 后为颜色 1 落子。
- 奇偶性天然成立：`to_move` 总是棋子较少（或相等）的一方，编为 color 1 后 `#color1 ≤ #color2`，piskvork 据奇偶判定 color 1 该走 → 引擎为 color 1 落子 = 为 `to_move` 落子。✅

### 6.3 router.py 改动（最小）

`next_move()` 在现有校验后：
```python
board = [row[:] for row in req.board]
# fast path：空棋盘天元（已有逻辑，保留）
# 主路径
move = await resolve_move(board, req.to_move, req.strength)
# resolve_move：尝试 Rapfi，失败回退 service.best_move(...)
```
回退时同步 `best_move` 用 `asyncio.to_thread` 包一层，避免阻塞事件循环。
新增：响应里 `engine` 字段标注 `"rapfi"` / `"python-fallback"`。

### 6.4 schemas.py 改动

- `NextMoveResponse` 增加可选字段 `engine: str = "rapfi"`。
- `MoveOut` 不变（`score/winning/blocks` 语义不变，`score` 仅用于排序展示，前端不依赖具体数值）。

## 7. API 契约（对外不变）

| 字段 | 来源 |
|---|---|
| `best` | Rapfi（或回退）落子点 |
| `top_moves` | `[best]`，按 `top_k` 用 best 补齐（沿用空棋盘补齐逻辑） |
| `best.winning` / `blocks` | 本地 `board.py` 计算（`would_win` / `would_complete_opp_win`） |
| `best.score` | Rapfi `INFO score` 解析值；拿不到填 0 |
| `elapsed_ms` | 端到端真实耗时（含进程启动） |
| `engine`（新，可选） | `"rapfi"` \| `"python-fallback"` |

错误码、请求字段、强度校验全部不变。

## 8. 部署（Docker 多阶段）

当前 `Dockerfile` 终态 `python:3.12-slim` 无编译器。新增 Rapfi 构建阶段：

```dockerfile
# --- 新增：Rapfi 构建 ---
FROM debian:bookworm-slim AS rapfi-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang cmake git build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# 钉死 tag/commit，保证可复现
ARG RAPFI_REF=<pinned-tag>
RUN git clone --depth 1 --branch ${RAPFI_REF} https://github.com/dhbloo/rapfi.git
WORKDIR /src/rapfi
# 按 README：x64-clang-AVX2 预设
RUN mkdir -p build/x64-clang-AVX2 && cd build/x64-clang-AVX2 \
    && cmake -DCMAKE_BUILD_TYPE=Release ../../.. \
    && cmake --build . -j"$(nproc)" --config Release
# 模型文件：随同 release 分发，构建阶段下载（ADD 校验 URL + sha256）
ARG RAPFI_MODEL_URL=<release-model-url>
ADD ${RAPFI_MODEL_URL} /model/
```

终态阶段追加（构建产物二进制名待实现期确认，可能是 `Rapfi` 或 `pbrain-Rapfi`，
用 shell 探测后统一拷成 `/opt/rapfi/pbrain-Rapfi`）：
```dockerfile
# 探测构建产物（CMake target 名因版本而异）并拷成固定路径
COPY --from=rapfi-build /src/rapfi/build/x64-clang-AVX2/ /tmp/rapfi-build/
RUN BIN=$(find /tmp/rapfi-build -maxdepth 1 -type f -perm -u+x \
        \( -name 'Rapfi' -o -name 'pbrain-Rapfi' \) | head -1) \
    && cp "$BIN" /opt/rapfi/pbrain-Rapfi && chmod +x /opt/rapfi/pbrain-Rapfi
COPY --from=rapfi-build /model/ /opt/rapfi/
```

- `Settings` 新增：`rapfi_bin_path=/opt/rapfi/pbrain-Rapfi`、`rapfi_model_dir=/opt/rapfi`、
  `rapfi_time_turn_weak/mid/strong`、`rapfi_max_memory_mb`、`rapfi_threads`。
- 运行时 `_has_avx2()` 探测；无 AVX2 → 自动回退 Python（容器照常起，五子棋不崩）。
- 镜像体积增量：Rapfi 二进制（~数 MB）+ 模型（~数 MB～数十 MB），可接受。

## 9. 错误处理与超时

- 子进程硬超时 = `time_turn + 3s`；超时 `proc.kill()` 并抛 `RapfiUnavailable`。
- 解析到非预期输出（无 `"x,y"` 行）→ `RapfiUnavailable`。
- 连续 3 次失败 → 进程内熔断，后续直接走 Python；`logging.warning`。
- **永不向客户端抛 500**：Rapfi 任何故障都回退，`engine` 字段如实标注。

## 10. 测试

- **`test_rapfi_protocol.py`**（不依赖真实 Rapfi 二进制，CI 稳定）：
  - 写一个 mock `pbrain` 脚本（bash/python），按协议回固定落子；验证：
    协议往返、坐标映射（输入构造 board → 期望输出坐标）、颜色映射、`START`/`INFO`/`BOARD…DONE` 顺序、超时 kill、解析容错（混入 `INFO`/`DEBUG` 行）、`END` 后进程退出。
  - monkeypatch `RAPFI_BIN` 指向 mock 脚本。
- **`test_gomoku_ai_router.py` 扩展**：`engine` 字段存在、`strength→time_turn` 映射、
  `is_rapfi_available()=False` 时走回退路径（monkeypatch）。
- **真实 Rapfi 冒烟**（本地/可选）：`.tool/gomoku_e2e.sh` 增加一段调真实二进制，打印落子与耗时；CI 跳过（CI 镜像未必带 AVX2）。

## 11. 前端

- `gomokuApi.js` / `GomokuPage.jsx` **不改**。
- 可选（非必须、后续）：UI 上显示 `engine` 字段（如 "Rapfi" 徽标）。

## 12. 风险与待验证项（实现期确认）

| 项 | 说明 | 处理 |
|---|---|---|
| `time_turn` 单位 | piskvork 历史上 ms / 厘秒混用 | 实现时按 Rapfi README 核对；用 2000 实测 ~2s 校验 |
| 模型文件名/路径约定 | Rapfi 从 CWD 或 `INFO folder` 找模型 | 设 `cwd=RAPFI_MODEL_DIR`；必要时 `INFO folder` |
| 预编译二进制备选 | 若 CI 源码编译耗时过长 | 退路：下载钉版预编译包 + sha256 校验 |
| Rapfi 在空棋盘经 BOARD 是否落子 | 个别引擎对空 BOARD 行为不一 | 已有空棋盘 fast path 直接返回天元，规避 |
| Windows 本地调试 | 开发机是 win32 | `_has_avx2()` 跨平台（win 读 `cpuinfo`/`wmic` 或默认 True）；本地可设 `RAPFI_BIN` 指向预编译 exe 调试 |

## 13. 相关文件

| 文件 | 职责 |
|---|---|
| `backend/src/rt_backend/gomoku_ai/rapfi.py`（新） | Rapfi 子进程 + BOARD 协议 + AVX2 探测 + 熔断 |
| `backend/src/rt_backend/gomoku_ai/router.py` | 调 `resolve_move`（Rapfi→回退） |
| `backend/src/rt_backend/gomoku_ai/schemas.py` | `NextMoveResponse.engine` |
| `backend/src/rt_backend/gomoku_ai/service.py` / `board.py` | 保留，作回退 + 算 winning/blocks |
| `backend/src/rt_backend/core/config.py` | 新增 rapfi_* 配置项 |
| `backend/tests/test_rapfi_protocol.py`（新） | 协议/坐标/颜色/超时/解析测试（mock 二进制） |
| `backend/tests/test_gomoku_ai_router.py` | 扩展回退与 engine 字段 |
| `Dockerfile` | 新增 rapfi-build 阶段 + COPY |
| `.tool/gomoku_e2e.sh` | 真实二进制冒烟（可选） |
