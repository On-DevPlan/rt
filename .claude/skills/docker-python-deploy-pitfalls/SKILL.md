---
name: docker-python-deploy-pitfalls
description: 当用户在 Docker 中部署 Python 后端（uv/pip + supervisord + nginx）遇到容器启动失败、502/500/404、TTS 服务崩溃等问题时触发。也适用于编辑 Python 服务器代码后部署异常的场景。
---

# Docker Python 后端部署避坑指南

基于 edge-tts + supervisord + nginx + Docker 部署的真实踩坑记录，共 10 个坑点。

## 一、路径类错误（最高频）

### 坑 1：supervisord command 路径与 Dockerfile COPY 不一致

**错误现象：** TTS 进程立即 exit status 2，supervisord 反复重启后放弃

**根因：** Dockerfile `COPY tts/ /app/tts/` 把文件放在 `/app/tts/` 下，但 supervisord.conf 写的 `command=python /app/tts_server.py`（少了 `tts/` 目录）

**规则：** supervisord command 的路径必须和 Dockerfile 的 COPY 目标路径严格对应

```
# Dockerfile
COPY tts/ /app/tts/          # 文件在 /app/tts/tts_server.py

# supervisord.conf — 正确
command=python /app/tts/tts_server.py

# supervisord.conf — 错误
command=python /app/tts_server.py
```

**预防：** 每次改 Dockerfile 的 COPY 或 supervisord 的 command 时，交叉检查另一个

### 坑 2：nginx proxy_pass 路径剥离

**错误现象：** 502 或 404，TTS 服务运行正常但请求到达不了正确的路由

**根因：** `location /tts` + `proxy_pass http://127.0.0.1:8080` 会把 `/tts/tts_with_timing` 原样转发，但 Python 服务器注册的路由是 `/tts_with_timing`（无前缀）

**规则：** 要剥离路径前缀，location 和 proxy_pass 都要加尾斜杠

```nginx
# 正确 — 剥离 /tts/ 前缀
location /tts/ {
    proxy_pass http://127.0.0.1:8080/;
}
# /tts/tts_with_timing → http://127.0.0.1:8080/tts_with_timing

# 错误 — 不剥离
location /tts {
    proxy_pass http://127.0.0.1:8080;
}
# /tts/tts_with_timing → http://127.0.0.1:8080/tts_with_timing（404，路由不存在）
```

## 二、依赖/工具类错误

### 坑 3：supervisord 用 uv run 但镜像里没有 uv

**错误现象：** TTS 进程 exit status 2（命令找不到）

**根因：** Dockerfile 用 `pip install` 或 `uv pip install --system` 安装依赖，但 supervisord.conf 改成了 `uv run`，而 `uv` 可执行文件不在 PATH 里

**规则：** supervisord command 必须和 Dockerfile 的安装方式匹配

| Dockerfile 安装方式 | supervisord command |
|---|---|
| `pip install edge-tts` | `python /app/tts/tts_server.py` |
| `uv pip install --system edge-tts` | `python /app/tts/tts_server.py` |
| 镜像里装了 uv | `uv run /app/tts/tts_server.py` |

**预防：** 改了 supervisord.conf 后，确认 Dockerfile 是否提供了对应的可执行文件

### 坑 4：编辑 Python 文件误删函数定义

**错误现象：** `NameError: name 'xxx_handler' is not defined`，整个模块加载失败

**根因：** 用 Edit 工具替换 `except` 块时，old_string 包含了下一行 `async def`，替换后函数定义消失

**规则：** 编辑 Python 文件后，检查替换区域的上下边界是否完整

```
# 危险操作：old_string 跨越了函数边界
except Exception as e:
    return web.json_response({"error": str(e)}, status=500)

async def voices_handler(request):    # ← 这行被吞掉了！
    voices = [...]

# 安全操作：只替换目标行
except Exception as e:
    return web.json_response({"error": str(e)}, status=500)
```

**预防：** 编辑后立即在文件中搜索被修改区域附近的函数定义，确认结构完整

## 三、部署脚本类错误

### 坑 5：SSH 嵌套 bash 单引号转义

**错误现象：** TTS 服务器收到 `JSONDecodeError: Expecting property name`，请求体解析失败

**根因：** SSH action 传递脚本时用 `bash -c '...'` 包裹，内层的 `'{"text":"test"}'` 单引号被外层吃掉，curl 发送了不合法的 JSON

**规则：** 在 `bash -c '...'` 内部，用 `\"` 转义双引号，不要用单引号包裹 JSON

```bash
# 错误 — 单引号被外层 bash -c '...' 吞掉
curl -d '{"text":"test"}'

# 正确 — 用双引号+转义
curl -d "{\"text\":\"test\"}"
```

### 坑 6：BusyBox sed 语法不兼容

**错误现象：** 部署脚本 `sed` 报错，打印完整 usage 帮助

**根因：** Alpine 镜像的 BusyBox sed 对 `$d` 的解析和 GNU sed 不同

**规则：** 在 Alpine/Docker 环境中，避免复杂的 sed 操作，用 `tail`/`head` 替代，或者用两次独立 curl 分别获取 body 和 status code

```bash
# 避免
BODY=$(echo "$RESP" | sed '$d')

# 替代方案
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" ...)
BODY=$(curl -s ...)
```

## 四、日志/调试类错误

### 坑 7：Python except 吞掉异常不输出日志

**错误现象：** TTS 返回 500，但 supervisord 的 stderr_logfile 为空，无法定位错误

**根因：** `except Exception as e: return web.json_response({"error": str(e)}, status=500)` 只把错误返回给客户端，没有输出到 stderr

**规则：** 所有 API handler 的 except 块必须同时打印 traceback

```python
import sys, traceback

except Exception as e:
    print(f"[handler_name] Error: {e}", file=sys.stderr, flush=True)
    traceback.print_exc(file=sys.stderr)
    return web.json_response({"error": str(e)}, status=500)
```

## 五、前端集成类错误

### 坑 8：isPlaying 被空数组 gate 导致高亮永远不触发

**错误现象：** TTS 音频正常返回，但页面没有单词高亮

**根因：** `isPlaying={isPlaying && revealedIndexes.includes(index)}`，`revealedIndexes` 初始化为 `[]` 且从未被填充

**规则：** 用专门的 `playingIndex` 状态追踪当前播放的句子，不要复用无关状态

```jsx
// 错误
isPlaying={isPlaying && revealedIndexes.includes(index)}

// 正确
const [playingIndex, setPlayingIndex] = useState(null)
isPlaying={isPlaying && playingIndex === index}
```

### 坑 9：hover 定时器声明了但没启动

**错误现象：** 悬浮句子 3 秒无反应，翻译不出现

**根因：** `intervalRef`/`timerRef` 声明了，但 `handleEnter` 只做了 `setActiveIndex(index)`，没有启动 setInterval/setTimeout

**规则：** 声明 ref 后，必须在对应的事件处理函数中启动/清理

### 坑 10：Audio data URI 对 edge_tts MP3 不可靠

**错误现象：** API 返回正确的 base64 音频数据，但 `new Audio()` 不播放，无报错

**根因：** edge_tts 输出的 MP3 格式可能包含 metadata，`data:audio/mp3;base64,...` 方式部分浏览器无法解码

**规则：** 使用 AudioContext.decodeAudioData 替代 data URI

```javascript
// 不可靠
const audio = new Audio(`data:audio/mp3;base64,${data.audio}`)

// 可靠
const bytes = new Uint8Array(atob(data.audio).split('').map(c => c.charCodeAt(0)))
const ctx = new AudioContext()
const buffer = await ctx.decodeAudioData(bytes.buffer)
const source = ctx.createBufferSource()
source.buffer = buffer
source.connect(ctx.destination)
source.start(0)
```

## 通用调试检查清单

遇到 Python 后端 Docker 部署失败时，按以下顺序排查：

1. **`docker logs <container>`** — 看 supervisord 输出，tts 是 RUNNING 还是 FATAL/EXITED
2. **路径对应** — Dockerfile COPY 目标 vs supervisord command vs nginx proxy_pass
3. **工具可用性** — supervisord command 用的可执行文件（python/uv）是否在镜像 PATH 里
4. **Python 语法完整性** — 编辑后确认所有函数定义存在（搜索 `async def`/`def`）
5. **nginx 路由** — curl 从容器内测试 `curl http://127.0.0.1:8080/tts_with_timing`
6. **SSH 引号转义** — 在 `bash -c '...'` 中用 `\"` 不用 `'"` 包 JSON
7. **错误日志** — Python except 块是否 print 到 stderr
8. **前端状态** — isPlaying/playingIndex/revealedIndexes 是否被正确设置和传递
