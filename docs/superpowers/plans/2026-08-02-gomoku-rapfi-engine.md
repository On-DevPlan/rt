# 五子棋 Rapfi 引擎接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把五子棋落子引擎从手写 1-ply Python 评估替换为 Rapfi（Gomocup 冠军引擎），对外 API 契约零改动，Rapfi 不可用时静默回退旧 Python 引擎。

**Architecture:** 每请求 spawn 一次 `pbrain-Rapfi` 子进程，走 Gomocup `BOARD` 协议设置全盘并取一手落子，然后 `END`/kill。新增纯函数模块 `gomoku_ai/rapfi.py` 承载子进程驱动、协议编解码、启动自检与熔断；router 在 Rapfi 可用时调用它，否则 `asyncio.to_thread` 回退 `service.best_move`。Docker 多阶段从源码编译 Rapfi AVX2 + 拉取 `Networks` 子模块权重。

**Tech Stack:** Python ≥3.12, FastAPI, pydantic-settings, pytest + pytest-asyncio（`asyncio_mode=auto`）, asyncio 子进程, CMake/clang（仅 Docker 构建期）, Rapfi（GPL v3, tag `250615`）。

## Global Constraints

- 对外接口 `POST /api/gomoku/next-move` 的请求字段与错误码**不变**；前端 `gomokuApi.js` 不改。
- 强度档位 1/2/3 → Rapfi `time_turn` 500/2000/5000 ms；旧 Python 引擎仅作回退，不暴露给前端选择。
- 协议坐标映射：Gomocup `"x,y"` 中 `x=列(col)`、`y=行(row)`、0 基；BOARD 颜色把 `to_move` 编为 `1`、对方编为 `2`。
- 测试必须确定性：协议/驱动测试用 **mock 二进制**（一个按协议回固定落子的脚本），不依赖真实 Rapfi（CI 无 Rapfi）。
- Rapfi 任何故障都回退 Python，**永不向客户端抛 500**；响应新增可选字段 `engine ∈ {"rapfi","python-fallback"}`。
- 配置走 pydantic-settings（env 可覆盖）：`rapfi_bin_path`、`rapfi_model_dir`、`rapfi_time_turn_weak/mid/strong`、`rapfi_max_memory_mb`、`rapfi_threads`、`rapfi_max_node`。
- Rapfi 为 GPL v3；本项目是自托管单机工具，不分发镜像即无开源披露义务（若日后分发镜像需附源码与 LICENSE）。
- 提交规范：每个 Task 结尾独立 commit；commit 信息中文，遵循仓库现有风格（参见 `git log`）。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/src/rt_backend/core/config.py` | 新增 rapfi_* 配置项 | Modify |
| `backend/src/rt_backend/gomoku_ai/rapfi.py` | Rapfi 子进程驱动 + 协议编解码 + 自检 + 熔断（纯函数，无 FastAPI） | Create |
| `backend/src/rt_backend/gomoku_ai/schemas.py` | `NextMoveResponse.engine` 字段 | Modify |
| `backend/src/rt_backend/gomoku_ai/router.py` | `resolve_move`：Rapfi→回退；`engine` 字段回填 | Modify |
| `backend/tests/conftest.py` | （若不存在则建）共享 fixture，暂无强制内容 | Create/Modify |
| `backend/tests/test_rapfi_protocol.py` | 纯函数编解码 + 子进程驱动 + 自检 + 熔断（mock 二进制） | Create |
| `backend/tests/test_gomoku_rapfi_wiring.py` | router 的 Rapfi/回退/engine 字段接线（monkeypatch） | Create |
| `Dockerfile` | 新增 `rapfi-build` 阶段 + COPY 二进制与权重 | Modify |
| `.tool/gomoku_e2e.sh` | 真实 Rapfi 冒烟（本地/可选，CI 跳过） | Modify |

---

## Task 1: 配置项 + rapfi.py 骨架与纯函数编解码

**Files:**
- Modify: `backend/src/rt_backend/core/config.py:7-22`（`Settings` 类内追加字段）
- Create: `backend/src/rt_backend/gomoku_ai/rapfi.py`
- Create: `backend/tests/test_rapfi_protocol.py`

**Interfaces:**
- Consumes: `rt_backend.core.config.get_settings`、`rt_backend.gomoku_ai.board.{SIZE,opponent}`
- Produces（后续 Task 依赖的签名，必须完全一致）:
  - `class RapfiUnavailable(Exception)`
  - `@dataclass(frozen=True) class RapfiMove: row:int; col:int; score:int; winning:bool; blocks:bool`
  - `def get_rapfi_command() -> list[str]`
  - `def get_model_dir() -> str`
  - `def board_to_gomocup_lines(board: list[list[int]], to_move: int) -> list[str]` —— 每行 `"<col>,<row>,<color>"`，`to_move`→1，对方→2
  - `def parse_gomocup_move(text: str) -> tuple[int, int] | None` —— 返回 `(row, col)`；非落子行（INFO/DEBUG/MESSAGE/OK/UNKNOWN/ERROR/空）或越界返回 `None`

- [ ] **Step 1: 写失败测试（纯函数编解码）**

`backend/tests/test_rapfi_protocol.py`：

```python
"""Tests for the Rapfi subprocess driver: protocol encoding/parsing,
subprocess round-trip, availability probe, circuit breaker.

Uses a mock pbrain script (no real Rapfi binary) so tests are deterministic
and run anywhere (including CI without AVX2).
"""
import asyncio
import os
import sys
import textwrap

import pytest

from rt_backend.gomoku_ai import rapfi
from rt_backend.gomoku_ai.rapfi import (
    RapfiMove,
    RapfiUnavailable,
    board_to_gomocup_lines,
    get_model_dir,
    get_rapfi_command,
    parse_gomocup_move,
)


# --- pure helpers ---------------------------------------------------------

def test_encode_to_move_becomes_color_one():
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1   # black
    board[7][8] = 2   # white
    lines = board_to_gomocup_lines(board, to_move=1)  # engine = black
    assert "7,7,1" in lines      # black -> color 1
    assert "8,7,2" in lines      # x=col=8, y=row=7, white -> color 2


def test_encode_to_move_white_swaps_colors():
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    board[7][8] = 2
    lines = board_to_gomocup_lines(board, to_move=2)  # engine = white
    assert "8,7,1" in lines      # white -> color 1
    assert "7,7,2" in lines      # black -> color 2


def test_encode_skips_empty_cells():
    board = [[0] * 15 for _ in range(15)]
    board[0][0] = 1
    lines = board_to_gomocup_lines(board, to_move=1)
    assert lines == ["0,0,1"]


def test_parse_move_returns_row_col_from_xy():
    assert parse_gomocup_move("3,5") == (5, 3)   # x=col=3, y=row=5 -> (row=5,col=3)


def test_parse_move_rejects_non_move_lines():
    for noise in ["", "OK", "UNKNOWN command", "DEBUG depth 4",
                  "INFO something", "MESSAGE hello", "ERROR bad"]:
        assert parse_gomocup_move(noise) is None


def test_parse_move_rejects_out_of_range():
    assert parse_gomocup_move("20,3") is None
    assert parse_gomocup_move("-1,3") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: FAIL（`ModuleNotFoundError: rt_backend.gomoku_ai.rapfi`）

- [ ] **Step 3: 加配置项**

编辑 `backend/src/rt_backend/core/config.py`，在 `tts_cache_db_path` 之后追加：

```python
    # --- Rapfi (gomoku engine) ---
    rapfi_bin_path: str = "/opt/rapfi/pbrain-Rapfi"
    rapfi_model_dir: str = "/opt/rapfi"
    rapfi_time_turn_weak: int = 500
    rapfi_time_turn_mid: int = 2000
    rapfi_time_turn_strong: int = 5000
    rapfi_max_memory_mb: int = 256
    rapfi_threads: int = 1
    rapfi_max_node: int = 10_000_000
```

- [ ] **Step 4: 写 rapfi.py 骨架与纯函数**

创建 `backend/src/rt_backend/gomoku_ai/rapfi.py`：

```python
"""Rapfi (Gomocup) engine driver: spawn-per-request subprocess + BOARD protocol.

Pure-Python module (no FastAPI/Pydantic). The router calls compute_move()
when is_rapfi_available() is True and falls back to the hand-written engine
otherwise. See docs/superpowers/specs/2026-08-02-gomoku-rapfi-engine-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.config import get_settings
from .board import SIZE


class RapfiUnavailable(Exception):
    """Raised when Rapfi cannot produce a move (binary missing, timeout,
    protocol error). The router catches this and falls back to the Python engine."""


@dataclass(frozen=True)
class RapfiMove:
    row: int
    col: int
    score: int
    winning: bool
    blocks: bool


def get_rapfi_command() -> List[str]:
    """Argv to launch Rapfi. Returned as a list so tests can swap in
    ``[sys.executable, mock_script]`` for a mock binary."""
    return [get_settings().rapfi_bin_path]


def get_model_dir() -> str:
    return get_settings().rapfi_model_dir


def board_to_gomocup_lines(board: List[List[int]], to_move: int) -> List[str]:
    """Encode the board as Gomocup BOARD-command stone lines.

    Each line is ``"<col>,<row>,<color>"`` where ``to_move`` becomes color 1
    (the side Rapfi plays) and the opponent becomes color 2. Empty cells are
    skipped. Order is irrelevant.
    """
    opp = 3 - to_move
    lines: List[str] = []
    for r in range(SIZE):
        for c in range(SIZE):
            v = board[r][c]
            if v == to_move:
                lines.append(f"{c},{r},1")
            elif v == opp:
                lines.append(f"{c},{r},2")
    return lines


def parse_gomocup_move(text: str) -> Optional[Tuple[int, int]]:
    """Parse a Gomocup move line ``"x,y"`` into ``(row=y, col=x)``.

    Returns None for non-move lines (INFO/DEBUG/MESSAGE/OK/UNKNOWN/ERROR/blank)
    and for coordinates outside the board. The ``int()`` parse plus range check
    is the entire filter — noise lines fail one of the two.
    """
    s = text.strip()
    parts = s.split(",")
    if len(parts) != 2:
        return None
    try:
        x, y = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    row, col = y, x
    if 0 <= row < SIZE and 0 <= col < SIZE:
        return row, col
    return None
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: PASS（6 tests）

- [ ] **Step 6: 提交**

```bash
git add backend/src/rt_backend/core/config.py \
        backend/src/rt_backend/gomoku_ai/rapfi.py \
        backend/tests/test_rapfi_protocol.py
git commit -m "feat(gomoku): rapfi 骨架与协议编解码纯函数 + 配置项"
```

---

## Task 2: 子进程驱动 compute_move + 熔断

**Files:**
- Modify: `backend/src/rt_backend/gomoku_ai/rapfi.py`（追加驱动逻辑）
- Modify: `backend/tests/test_rapfi_protocol.py`（追加驱动测试）

**Interfaces:**
- Consumes: Task 1 的 `get_rapfi_command`、`get_model_dir`、`board_to_gomocup_lines`、`parse_gomocup_move`、`RapfiMove`、`RapfiUnavailable`；`board.{would_win, would_complete_opp_win, opponent}`
- Produces:
  - `async def compute_move(board, to_move, time_turn_ms, *, timeout_s: float) -> RapfiMove`
  - `def _record_failure() -> None`、`def _record_success() -> None`、`def _reset_state_for_tests() -> None`、模块级 `_disabled: bool`、`_fail_count: int`

- [ ] **Step 1: 追加失败测试（mock 二进制驱动）**

在 `tests/test_rapfi_protocol.py` 末尾追加：

```python
# --- subprocess driver (mock binary) --------------------------------------

NORMAL_MOCK = """\
import sys
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            sys.stdout.write('OK\\n'); sys.stdout.flush()
        elif c.startswith('INFO'):
            pass
        elif c == 'BOARD':
            n = 0
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
                n += 1
            sys.stdout.write('DEBUG saw %d stones\\n' % n)
            sys.stdout.write('3,3\\n')   # x=col=3, y=row=3
            sys.stdout.flush()
        elif c == 'END':
            return
main()
"""

HANG_MOCK = """\
import sys, time
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            sys.stdout.write('OK\\n'); sys.stdout.flush()
        elif c == 'BOARD':
            # drain stones until DONE, then never answer
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
            time.sleep(30)
        elif c == 'END':
            return
main()
"""

GARBAGE_MOCK = """\
import sys
def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        c = line.strip()
        if c.startswith('START'):
            sys.stdout.write('OK\\n'); sys.stdout.flush()
        elif c == 'BOARD':
            while True:
                l = sys.stdin.readline()
                if not l or l.strip() == 'DONE':
                    break
            sys.stdout.write('ERROR no weights\\n')
            sys.stdout.flush()
            return
        elif c == 'END':
            return
main()
"""


def _write_mock(tmp_path, body: str):
    p = tmp_path / "mock_pbrain.py"
    p.write_text(body, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _reset_rapfi_state():
    rapfi._reset_state_for_tests()
    yield
    rapfi._reset_state_for_tests()


def _patch_cmd(monkeypatch, mock_path):
    monkeypatch.setattr(rapfi, "get_rapfi_command", lambda: [sys.executable, str(mock_path)])
    monkeypatch.setattr(rapfi, "get_model_dir", lambda: str(mock_path.parent))


async def test_compute_move_round_trip_returns_parsed_move(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    mv = await rapfi.compute_move(board, to_move=2, time_turn_ms=500, timeout_s=5.0)
    assert isinstance(mv, RapfiMove)
    assert (mv.row, mv.col) == (3, 3)
    assert mv.winning is False
    assert mv.blocks is False


async def test_compute_move_marks_winning_and_blocks(tmp_path, monkeypatch):
    # Make the mock report a move at a square that wins for black / blocks white.
    winning_mock = NORMAL_MOCK.replace("3,3", "7,9")
    _patch_cmd(monkeypatch, _write_mock(tmp_path, winning_mock))
    board = [[0] * 15 for _ in range(15)]
    for c in range(5, 9):       # black four in a row, col 5..8 at row 7
        board[7][c] = 1
    mv = await rapfi.compute_move(board, to_move=1, time_turn_ms=500, timeout_s=5.0)
    assert (mv.row, mv.col) == (7, 9)
    assert mv.winning is True   # playing (7,9) completes five for black


async def test_compute_move_timeout_raises_unavailable(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, HANG_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    with pytest.raises(RapfiUnavailable):
        await rapfi.compute_move(board, to_move=2, time_turn_ms=500, timeout_s=0.5)


async def test_compute_move_no_move_line_raises_unavailable(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, GARBAGE_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    with pytest.raises(RapfiUnavailable):
        await rapfi.compute_move(board, to_move=2, time_turn_ms=500, timeout_s=3.0)


async def test_circuit_breaker_trips_after_three_failures(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, GARBAGE_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    for _ in range(3):
        with pytest.raises(RapfiUnavailable):
            await rapfi.compute_move(board, to_move=2, time_turn_ms=500, timeout_s=1.0)
    assert rapfi._disabled is True
    assert rapfi.is_rapfi_available() is False


async def test_success_resets_failure_counter(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    board = [[0] * 15 for _ in range(15)]
    board[7][7] = 1
    await rapfi.compute_move(board, to_move=2, time_turn_ms=500, timeout_s=5.0)
    assert rapfi._fail_count == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: FAIL（`compute_move` / `_reset_state_for_tests` 未定义）

- [ ] **Step 3: 实现 compute_move 与熔断**

在 `rapfi.py` 顶部 import 区追加：

```python
import asyncio
import os
```

并把 `from .board import SIZE` 改为：

```python
from .board import (
    SIZE,
    opponent,
    would_complete_opp_win,
    would_win,
)
```

在文件末尾追加：

```python
# --- circuit breaker ------------------------------------------------------

_disabled: bool = False
_fail_count: int = 0
_FAIL_THRESHOLD = 3


def _record_failure() -> None:
    global _disabled, _fail_count
    _fail_count += 1
    if _fail_count >= _FAIL_THRESHOLD:
        _disabled = True


def _record_success() -> None:
    global _disabled, _fail_count
    _fail_count = 0
    _disabled = False


def _reset_state_for_tests() -> None:
    global _disabled, _fail_count
    _disabled = False
    _fail_count = 0


# --- subprocess driver ----------------------------------------------------

async def _read_move(stdout: asyncio.StreamReader) -> Tuple[int, int]:
    while True:
        raw = await stdout.readline()
        if not raw:
            raise RapfiUnavailable("rapfi closed stdout without a move")
        text = raw.decode("utf-8", "replace").strip()
        mv = parse_gomocup_move(text)
        if mv is not None:
            return mv


async def _drain(proc: asyncio.subprocess.Process, timeout_s: float) -> None:
    """END the engine and reap it, killing on timeout."""
    try:
        proc.stdin.write(b"END\n")
        await proc.stdin.drain()
    except Exception:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _compute_move_inner(board, to_move, time_turn_ms, timeout_s):
    cmd = get_rapfi_command()
    s = get_settings()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=get_model_dir(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise RapfiUnavailable(f"cannot launch rapfi: {e}")

    assert proc.stdin is not None and proc.stdout is not None
    try:
        w = proc.stdin.write
        w(b"START 15\n")
        w(f"INFO time_turn {time_turn_ms}\n".encode())
        w(f"INFO max_memory {s.rapfi_max_memory_mb}\n".encode())
        w(f"INFO number_of_threads {s.rapfi_threads}\n".encode())
        w(f"INFO max_node {s.rapfi_max_node}\n".encode())
        w(b"BOARD\n")
        for line in board_to_gomocup_lines(board, to_move):
            w(line.encode() + b"\n")
        w(b"DONE\n")
        await proc.stdin.drain()

        row, col = await asyncio.wait_for(_read_move(proc.stdout), timeout=timeout_s)
    finally:
        await _drain(proc, timeout_s)

    return RapfiMove(
        row=row,
        col=col,
        score=0,
        winning=would_win(board, row, col, to_move),
        blocks=would_complete_opp_win(board, row, col, opponent(to_move)),
    )


async def compute_move(board, to_move, time_turn_ms, *, timeout_s: float) -> RapfiMove:
    """Run one Rapfi subprocess, set the full board via BOARD, return its move.

    Any failure (launch error, timeout, no move line) is recorded against the
    circuit breaker and re-raised as RapfiUnavailable.
    """
    try:
        mv = await _compute_move_inner(board, to_move, time_turn_ms, timeout_s)
    except RapfiUnavailable:
        _record_failure()
        raise
    except Exception as e:  # subprocess / decode surprises
        _record_failure()
        raise RapfiUnavailable(str(e)) from e
    _record_success()
    return mv
```

> 还需要 `get_settings` 在文件内可见 —— Task 1 已 `from ..core.config import get_settings`，确认仍在 import 区。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: PASS（13 tests：6 编解码 + 7 驱动/熔断）

- [ ] **Step 5: 提交**

```bash
git add backend/src/rt_backend/gomoku_ai/rapfi.py backend/tests/test_rapfi_protocol.py
git commit -m "feat(gomoku): rapfi 子进程驱动 compute_move 与熔断"
```

---

## Task 3: is_rapfi_available() 启动自检

**Files:**
- Modify: `backend/src/rt_backend/gomoku_ai/rapfi.py`（追加自检）
- Modify: `backend/tests/test_rapfi_protocol.py`（追加自检测试）

**Interfaces:**
- Consumes: Task 2 的 `compute_move`、`_reset_state_for_tests`、`get_rapfi_command`、`get_model_dir`
- Produces: `async def is_rapfi_available() -> bool`（router 内 await）、`async def _probe() -> bool`、模块级 `_availability: Optional[bool]`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_rapfi_protocol.py` 末尾追加：

```python
# --- availability probe ---------------------------------------------------

async def test_probe_unavailable_when_binary_missing(monkeypatch):
    monkeypatch.setattr(rapfi, "get_rapfi_command",
                        lambda: ["/nonexistent/path/pbrain-Rapfi"])
    monkeypatch.setattr(rapfi, "get_model_dir", lambda: "/tmp")
    rapfi._reset_state_for_tests()
    assert await rapfi.is_rapfi_available() is False


async def test_probe_unavailable_when_circuit_open(monkeypatch):
    rapfi._disabled = True
    monkeypatch.setattr(rapfi, "get_rapfi_command",
                        lambda: [sys.executable, "does-not-matter"])
    assert await rapfi.is_rapfi_available() is False


async def test_probe_available_when_mock_responds(tmp_path, monkeypatch):
    _patch_cmd(monkeypatch, _write_mock(tmp_path, NORMAL_MOCK))
    rapfi._reset_state_for_tests()
    assert await rapfi.is_rapfi_available() is True
    # cached: second call does not re-probe
    assert await rapfi.is_rapfi_available() is True
```

> `is_rapfi_available()` 是 **async**（生产里在 async endpoint 内 await），因此测试用
> `async def` 并 `await`；pytest-asyncio `auto` 模式自动驱动。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: FAIL（`is_rapfi_available` 未定义）

- [ ] **Step 3: 实现自检**

在 `rapfi.py` 追加：

```python
# --- availability probe ---------------------------------------------------

_availability: Optional[bool] = None


def _binary_exists() -> bool:
    path = get_rapfi_command()[0]
    return os.path.isfile(path)


async def _probe() -> bool:
    """Run one trivial round-trip on a near-empty board. True if Rapfi
    returns a sane move, False on any RapfiUnavailable."""
    if not _binary_exists():
        return False
    board = [[0] * SIZE for _ in range(SIZE)]
    board[SIZE // 2][SIZE // 2] = 1
    try:
        await compute_move(board, to_move=2, time_turn_ms=200, timeout_s=4.0)
        return True
    except RapfiUnavailable:
        return False


async def is_rapfi_available() -> bool:
    """True iff Rapfi is usable. Lazy: probes once on first call and caches.

    A successful probe sets availability True; the circuit breaker can still
    disable it at runtime via _disabled. Reset with _reset_state_for_tests().
    Must be awaited — the router calls it inside the async endpoint, so the
    probe runs on the request's own event loop (no run_until_complete gymnastics).
    """
    global _availability
    if _disabled:
        return False
    if _availability is None:
        try:
            _availability = await _probe()
        except Exception:
            _availability = False
    return bool(_availability)
```

并把 `_reset_state_for_tests` 扩展为同时清缓存：

```python
def _reset_state_for_tests() -> None:
    global _disabled, _fail_count, _availability
    _disabled = False
    _fail_count = 0
    _availability = None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_rapfi_protocol.py -v`
Expected: PASS（16 tests）

- [ ] **Step 5: 跑全量回归确认未破坏其它测试**

Run: `cd backend && PYTHONPATH=src uv run pytest -q`
Expected: 全绿（既有 gomoku/router/service 测试不受影响）

- [ ] **Step 6: 提交**

```bash
git add backend/src/rt_backend/gomoku_ai/rapfi.py backend/tests/test_rapfi_protocol.py
git commit -m "feat(gomoku): rapfi is_rapfi_available 启动自检"
```

---

## Task 4: schema engine 字段 + router 接线与回退

**Files:**
- Modify: `backend/src/rt_backend/gomoku_ai/schemas.py:44-48`（`NextMoveResponse`）
- Modify: `backend/src/rt_backend/gomoku_ai/router.py`（`next_move` 改用 `resolve_move`）
- Create: `backend/tests/test_gomoku_rapfi_wiring.py`

**Interfaces:**
- Consumes: `rapfi.{compute_move, is_rapfi_available, RapfiUnavailable, RapfiMove}`、`service.{best_move, top_moves}`、`board.{has_any_stone, CENTER}`
- Produces: `async def _resolve_move(board, to_move, strength) -> Tuple[Move|RapfiMove, str]`

- [ ] **Step 1: 写失败测试（接线 + engine 字段）**

`backend/tests/test_gomoku_rapfi_wiring.py`：

```python
"""Router wiring: Rapfi path sets engine='rapfi'; fallback sets
'python-fallback'. Availability is monkeypatched so tests are deterministic."""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.gomoku_ai import rapfi, router as gomoku_router
from rt_backend.gomoku_ai.rapfi import RapfiMove
from rt_backend.gomoku_ai.router import build_router

EMPTY = [[0] * 15 for _ in range(15)]


async def _avail_true() -> bool:
    return True


async def _avail_false() -> bool:
    return False


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(build_router())
    return TestClient(app)


def _board_with_one_stone():
    b = [row[:] for row in EMPTY]
    b[7][7] = 1
    return b


def test_rapfi_path_sets_engine_label(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def fake_compute(board, to_move, time_turn_ms, *, timeout_s):
        return RapfiMove(row=7, col=8, score=0, winning=False, blocks=False)

    monkeypatch.setattr(gomoku_router, "compute_move", fake_compute)
    r = client.post("/api/gomoku/next-move",
                    json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 3})
    assert r.status_code == 200
    j = r.json()
    assert j["engine"] == "rapfi"
    assert (j["best"]["row"], j["best"]["col"]) == (7, 8)
    assert len(j["top_moves"]) == 3
    assert all((m["row"], m["col"]) == (7, 8) for m in j["top_moves"])


def test_fallback_when_rapfi_unavailable(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_false)
    r = client.post("/api/gomoku/next-move",
                    json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 3})
    assert r.status_code == 200
    j = r.json()
    assert j["engine"] == "python-fallback"
    assert 0 <= j["best"]["row"] < 15


def test_fallback_when_rapfi_raises(client, monkeypatch):
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def boom(board, to_move, time_turn_ms, *, timeout_s):
        raise rapfi.RapfiUnavailable("simulated")

    monkeypatch.setattr(gomoku_router, "compute_move", boom)
    r = client.post("/api/gomoku/next-move",
                    json={"board": _board_with_one_stone(), "to_move": 2, "top_k": 1})
    assert r.status_code == 200
    assert r.json()["engine"] == "python-fallback"


def test_strength_maps_to_time_turn(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(gomoku_router, "is_rapfi_available", _avail_true)

    async def capture(board, to_move, time_turn_ms, *, timeout_s):
        seen["t"] = time_turn_ms
        return RapfiMove(row=7, col=8, score=0, winning=False, blocks=False)

    monkeypatch.setattr(gomoku_router, "compute_move", capture)
    client.post("/api/gomoku/next-move",
                json={"board": _board_with_one_stone(), "to_move": 2, "strength": 3, "top_k": 1})
    assert seen["t"] == 5000  # strong tier
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_gomoku_rapfi_wiring.py -v`
Expected: FAIL（`engine` 字段不存在 / `compute_move` 未在 router 命名空间）

- [ ] **Step 3: schema 加 engine 字段**

编辑 `schemas.py` 的 `NextMoveResponse`：

```python
class NextMoveResponse(BaseModel):
    best: MoveOut
    top_moves: List[MoveOut]
    elapsed_ms: float
    engine: str = "rapfi"
```

- [ ] **Step 4: router 接线**

编辑 `router.py`：在 import 区把

```python
from .service import Move, best_move, top_moves
```

改为

```python
import asyncio

from .board import has_any_stone
from .rapfi import RapfiUnavailable, compute_move, is_rapfi_available
from .service import Move, best_move, top_moves
```

并在 `build_router` 内、`@router.post("/next-move" ...)` 之前插入辅助函数：

```python
    from ..core.config import get_settings

    _TIME_BY_STRENGTH = lambda: {
        1: get_settings().rapfi_time_turn_weak,
        2: get_settings().rapfi_time_turn_mid,
        3: get_settings().rapfi_time_turn_strong,
    }

    async def _resolve_move(board, to_move, strength):
        """Try Rapfi; fall back to the Python engine on any failure.
        Returns (move, engine_label)."""
        time_turn = _TIME_BY_STRENGTH()[strength]
        if await is_rapfi_available():
            timeout = time_turn / 1000.0 + 3.0
            try:
                mv = await compute_move(board, to_move, time_turn, timeout_s=timeout)
                return mv, "rapfi"
            except RapfiUnavailable:
                pass
        mv = await asyncio.to_thread(best_move, board, to_move, strength=strength)
        return mv, "python-fallback"
```

然后把 `next_move` 的核心（现有 `best = best_move(...)` / `alts = top_moves(...)` 段）替换为：

```python
        if has_any_stone(board):
            best, engine = await _resolve_move(board, req.to_move, req.strength)
            if engine == "rapfi":
                alts = [best] * req.top_k
            else:
                alts = top_moves(board, req.to_move, k=req.top_k, strength=req.strength)
        else:
            # empty board fast path: center, no subprocess
            best = best_move(board, req.to_move, strength=req.strength)
            alts = top_moves(board, req.to_move, k=req.top_k, strength=req.strength)
            engine = "python-fallback"

        return NextMoveResponse(
            best=_to_row_col(best),
            top_moves=[_to_row_col(m) for m in alts],
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            engine=engine,
        )
```

> `_to_row_col` 已用属性访问（`.row` 等），`RapfiMove` 与 `service.Move` 均满足，无需改动。

- [ ] **Step 5: 跑接线测试确认通过**

Run: `cd backend && PYTHONPATH=src uv run pytest tests/test_gomoku_rapfi_wiring.py -v`
Expected: PASS（4 tests）

- [ ] **Step 6: 跑全量回归**

Run: `cd backend && PYTHONPATH=src uv run pytest -q`
Expected: 全绿。既有 `test_gomoku_ai_router.py`（无 Rapfi 二进制 → `is_rapfi_available()` 返回 False → 走回退）保持原行为。

- [ ] **Step 7: 提交**

```bash
git add backend/src/rt_backend/gomoku_ai/schemas.py \
        backend/src/rt_backend/gomoku_ai/router.py \
        backend/tests/test_gomoku_rapfi_wiring.py
git commit -m "feat(gomoku): router 接线 Rapfi 并保留 Python 回退 + engine 字段"
```

---

## Task 5: Docker 多阶段构建 Rapfi（AVX2 + 权重）

**Files:**
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: Task 1 的默认配置路径 `/opt/rapfi/pbrain-Rapfi`、`/opt/rapfi`
- Produces: 镜像内可执行的 `pbrain-Rapfi` + 同目录权重/配置；运行时 `is_rapfi_available()` 自检通过即启用 Rapfi

> 说明：本 Task 无 pytest；验证手段是 `docker build` 成功 + 容器内跑一次 `pbrain-Rapfi` BOARD 往返。权重/配置的精确布局是本方案唯一需在构建期实测确认的细节（见 Step 4 的核对与修正）。

- [ ] **Step 1: 在现有 `Dockerfile` 顶部（`FROM node:20-alpine AS frontend` 之前）插入 Rapfi 构建阶段**

```dockerfile
# Stage 0: build Rapfi engine (AVX2) + fetch NNUE weights from the Networks submodule
FROM debian:bookworm-slim AS rapfi-build
RUN apt-get update && apt-get install -y --no-install-recommends \
        clang cmake git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG RAPFI_REF=250615
WORKDIR /src
RUN git clone --depth 1 --branch ${RAPFI_REF} https://github.com/dhbloo/rapfi.git \
    && cd rapfi \
    && git submodule update --init --depth 1 Networks
WORKDIR /src/rapfi/Rapfi
RUN mkdir -p build/avx2 && cd build/avx2 \
    && cmake ../.. \
        -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_BUILD_TYPE=Release \
        -DUSE_SSE=ON -DUSE_AVX2=ON -DUSE_AVX512=OFF -DUSE_BMI2=OFF -DUSE_VNNI=OFF \
    && cmake --build . -j"$(nproc)"
# Assemble engine dir: binary + config + all NNUE/classical weights flat together
RUN mkdir -p /out \
    && cp build/avx2/Rapfi /out/pbrain-Rapfi \
    && chmod +x /out/pbrain-Rapfi \
    && cp /src/rapfi/Networks/config-example/config.toml /out/config.toml \
    && cp /src/rapfi/Networks/mix9svq/*.bin.lz4 /out/ \
    && cp /src/rapfi/Networks/classical/model220723.bin /out/
```

- [ ] **Step 2: 在最终阶段（`FROM python:3.12-slim` 之后、`WORKDIR /app/backend` 之前）拷入 Rapfi**

在现有 `COPY nginx.conf /etc/nginx/nginx.conf` 附近追加：

```dockerfile
COPY --from=rapfi-build /out/ /opt/rapfi/
```

- [ ] **Step 3: 本地构建镜像**

Run: `docker build -t rt:rapfi-test .`
Expected: 构建成功，无报错。若 `git submodule update --init Networks` 失败（浅克隆偶发），改为在 rapfi-build 阶段追加：
`RUN git clone --depth 1 https://github.com/dhbloo/rapfi-networks.git /src/rapfi/Networks` 并重跑。

- [ ] **Step 4: 容器内自检 Rapfi 能加载权重并落子**

Run:
```bash
docker run --rm rt:rapfi-test sh -c '
  cd /opt/rapfi
  printf "START 15\nBOARD\n7,7,1\nDONE\nEND\n" | ./pbrain-Rapfi 2>&1 | head -20
'
```
Expected: 输出中含一行形如 `"<x>,<y>"` 的落子（白方应手），且**无** `ERROR`/`cannot find`/`weights` 缺失字样。

**若报缺权重/配置路径**：`cat /opt/rapfi/config.toml`（容器内）查看其中 `weight`/`path` 字段引用的文件名；按其引用把权重放到对应相对路径（多半 config 引用裸文件名，flat 拷贝已满足；若引用子目录则在 `/opt/rapfi/` 下建同名子目录再拷）。修正后重跑 Step 3–4。

**若落子耗时明显偏离 time_turn（如请求 500 实际 ~5s）**：`INFO time_turn` 单位是厘秒而非毫秒，把 `TIME_BY_STRENGTH` 三个默认值除以 10 写回 `config.py`（即 50/200/500），重跑测试。

- [ ] **Step 5: 容器内验证后端端到端**

Run（容器起后端 + 一个请求）：
```bash
docker run --rm -d -p 8096:80 --name rt-rapfi rt:rapfi-test
sleep 3
curl -s -X POST http://127.0.0.1:8096/api/gomoku/next-move \
  -H 'Content-Type: application/json' \
  -d '{"board": [[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]], "to_move": 2, "strength": 2}'
docker rm -f rt-rapfi
```
Expected: HTTP 200，JSON 含 `"engine":"rapfi"`，`best.row/col` 在 0..14。

- [ ] **Step 6: 提交**

```bash
git add Dockerfile
git commit -m "build(docker): 多阶段编译 Rapfi AVX2 并打入权重"
```

---

## Task 6（可选）: 真实 Rapfi 端到端冒烟脚本

**Files:**
- Modify: `.tool/gomoku_e2e.sh`

> 仅本地手测用；CI 不跑（无 AVX2/无 Rapfi）。在已有脚本末尾追加。

- [ ] **Step 1: 追加冒烟段**

在 `.tool/gomoku_e2e.sh` 的 python heredoc 之后、`echo done` 之前插入：

```bash
echo "--- Rapfi 真机冒烟（需容器已构建且 CPU 支持 AVX2）---"
docker run --rm rt:rapfi-test sh -c '
  cd /opt/rapfi
  printf "START 15\nBOARD\n7,7,1\n7,8,2\nDONE\nEND\n" | ./pbrain-Rapfi 2>&1 | tail -3
'
```

- [ ] **Step 2: 手动运行确认**

Run: `bash .tool/gomoku_e2e.sh`
Expected: 末尾打印一行 `"<x>,<y>"` 落子（黑 7,7 / 白 7,8 之后的黑方应手）。

- [ ] **Step 3: 提交**

```bash
git add .tool/gomoku_e2e.sh
git commit -m "test(gomoku): 追加真实 Rapfi 冒烟段"
```

---

## 完成标准 (Definition of Done)

- [ ] `cd backend && PYTHONPATH=src uv run pytest -q` 全绿。
- [ ] 对外 `POST /api/gomoku/next-move` 请求/响应字段与错误码与 `docs/api-gomoku.md` 一致（仅新增可选 `engine`）。
- [ ] 容器内 Rapfi 自检通过 → 实际对弈由 Rapfi 落子；卸载/缺 AVX2 → 自动回退 Python，不报 500。
- [ ] `docs/api-gomoku.md` 的"算法概述"节补充一句：落子引擎为 Rapfi（Gomocup），不可用时回退内置评估（见 Task 4 之后的文档小更新，可并入该 commit）。
