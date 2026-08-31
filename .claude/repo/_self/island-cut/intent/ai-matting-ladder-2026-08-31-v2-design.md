# Intent: AI 抠图升级阶梯（L0→L4）预测设计（v2 — L1 实施细化版）

> **Date:** 2026-08-31
> **Topic:** island-cut
> **类型:** intent doc（预测设计）
> **版本:** v2（相对 v1：**推翻** L1 的"rembg 包"选型 → 直连 onnxruntime + u2netp.onnx；**推翻** v1 改动范围表中的 docker-compose 假设 → 沿用现有 CI 裸 docker run 部署；**细化** L1 为可实施设计（sync httpx、缓存键、软 alpha、capabilities 端点）；L2-L4 阶梯定义原样保留）
> **状态:** 候选（L1 选型已过用户拍板，实施计划已批准，因暂停未动工）
> **核心问题:** 在 2C2G/Docker/主服务 ≤300MB 的硬约束下，把 L1（u2netp sidecar）落成可实施、可回退的设计。

相关文档：[ai-matting-ladder-2026-08-31-v1-design.md](./ai-matting-ladder-2026-08-31-v1-design.md)（v1，保留） · [compare_matting-libraries-2026-08-31-v1-status.md](../project/compare_matting-libraries-2026-08-31-v1-status.md) · [interior-white-region-2026-08-31-v2-design.md](./interior-white-region-2026-08-31-v2-design.md)（下游正交功能） · [island-cut-params-2026-08-31-v1-concepts.md](../project/island-cut-params-2026-08-31-v1-concepts.md)（参数体系指称表）

## 本版要验证的假设

1. 直连方案（onnxruntime+numpy+pillow + u2netp.onnx）在 mem_limit 384m 容器内稳定推理不 OOM（调研估 RSS 120-200MB，待服务器实测）。
2. mask 契约不变（`POST /matte` → L 灰度 mask PNG）时，主服务下游（closing→label→岛切→白区）对 mask 来源零感知——ai 模式产出结构合法的岛切结果。
3. sync `httpx.Client` 在 sync def 端点（线程池）下调用 sidecar 不阻塞事件循环，3s 超时 + 降级使故障面不扩大。
4. sha256(原图字节)+model+边长 为键的磁盘缓存，对单人反复调参场景命中率足够高（同图二次请求不打 sidecar）。

## 一、设计原则（L1 落地版）

| # | 原则 | 体现 |
| - | --- | --- |
| 1 | mask 来源可插拔（继承 v1） | `mode="ai"` 只是 fg 的第三种来源，下游五段流水线零改动 |
| 2 | OOM 隔离（继承 v1） | AI 只跑独立 sidecar，`--memory 384m --memory-swap 384m`；主服务不装 onnxruntime |
| 3 | 直连零重依赖（v2 新增，推翻 v1 的 rembg 选型） | sidecar 只装 onnxruntime+numpy+pillow+fastapi+uvicorn；rembg 2.0.81 的 pymatting/numba/scipy/skimage 是 import 期硬依赖（详见决策 1），直连方案 RSS 减半以上 |
| 4 | 降级而非失败（继承 v1） | sidecar 超时/5xx/连接拒绝 → 原图走 auto 通路重切 + 响应 `ai_fallback: true` |
| 5 | 模型进镜像（继承 v1） | 构建期从 rembg release 下载 u2netp.onnx + md5 校验，运行时零下载 |
| 6 | 部署沿用现有模式（v2 新增，推翻 v1 的 compose 假设） | 现状 CI 是 save→SCP→ssh 裸 docker run（无 compose），第二镜像照此办理 + 幂等 `docker network create`；不顺带重构部署模型 |
| 7 | 主服务不新增依赖（继承 v1） | httpx 已在 backend 依赖里，matte_client 用 sync Client |

## 二、模块拆分

```
backend/src/rt_backend/island_cut/
├── matte_client.py   # 新增：MatteClient（sync httpx.Client）+ sha256 磁盘缓存 + TTL 清理
│                     #   常量 MODEL="u2netp"、LONG_EDGE=640
├── service.py        # run_cut 增 ai_mask 参数：fg = ai_mask > alpha_threshold；
│                     #   _crop_piece 增 ai 分支（grow(mask) 内写软 alpha）
├── schemas.py        # mode Literal 增 "ai"；CutResponse 增 ai_fallback: bool = False
├── router.py         # build_router(store_provider, matte_provider)；ai 流程 + 降级；
│                     #   GET /capabilities → {"ai_matting": bool}（按配置判定，不 ping）
└── tests（tests/test_matte_client.py 新增 + test_island_cut.py 增 ai 用例）
backend/src/rt_backend/core/config.py   # +island_cut_ai_url / _timeout_sec(3.0)
                                        #   / _cache_dir(空→tempdir) / _cache_ttl_min(1440)
backend/src/rt_backend/main.py          # lifespan：url 非空则建 MatteClient 挂 app.state.matte

docker/island-cut-ai/                   # sidecar（独立镜像，直连方案）
├── server.py         # POST /matte（raw bytes body）→ mask PNG；GET /health；无状态
├── requirements.txt  # onnxruntime==1.23.2 / numpy / pillow / fastapi / uvicorn（无 multipart）
└── Dockerfile        # python:3.12-slim；构建期 python urlretrieve 下载 u2netp.onnx + md5 校验；
                      #   ENV OMP_NUM_THREADS=1；EXPOSE 8100

.github/workflows/deploy.yml           # 第二镜像 build/save/scp；SSH script：幂等 docker network
                                       #   create rt-net；sidecar --memory 384m；rt_app 加
                                       #   --network rt-net -e ISLAND_CUT_AI_URL=...；健康检查加 exec curl
.dockerignore                          # +backend/.venv（既有隐患：Windows venv 被 COPY 进 Linux 镜像）
src/modules/island-cut/                # capabilities 探测 + AI chip 置灰 + ai_fallback 标签
```

## 三、数据流（关键场景）

**场景 A：ai 切分成功**

上传 → `create_job`（mode="ai"）→ `MatteClient.get_mask(bytes)`：缓存键 `sha256(原bytes):u2netp:640` 查临时目录 → miss → `resample`（PIL 长边 ≤640 等比 PNG 重编码）→ `POST {url}/matte`（octet-stream）→ L 灰度 mask PNG → 存缓存 → `upsample`（LANCZOS 回原尺寸，uint8 0..255）→ `run_cut(rgba, params, ai_mask=…)`：`fg = ai_mask > alpha_threshold` → 既有 closing/label/岛切 → 响应 `mode="ai"`。

**场景 B：sidecar 故障降级**

超时（默认 3s）/非 200/连接拒绝 → log warning → `get_mask` 返回 None → 原字节走既有 auto 判定（detect_mode → alpha/white 通路）重切 → 响应 `mode="alpha"|"white"` + `ai_fallback: true`。url 为空（未部署）→ `HTTPException 503 "AI 抠图未部署"`（前端 capabilities 探测后 chip 置灰，正常流不会打到这）。

**场景 C：缓存命中**

同图二次请求 → 缓存命中 → 不打 sidecar → 直接 upsample → 切割。调参（closing/min_area 等）反复重切时 sidecar 零负载。

## 四、关键决策（含选型说明；标注 ✓ 的为用户已拍板）

1. **✓ sidecar 直连 onnxruntime，不用 rembg 包**。理由（2026-08 调研，来源见 §十一）：rembg 2.0.81 base 依赖含 `pymatting>=1.1.14`（连带 numba/llvmlite）、`scikit-image`、`scipy`，且 `bg.py` 顶层 import——不装连 `from rembg import remove` 都 ImportError，**无法通过 extras 绕过**；全家桶容器 RSS 估 250-400MB（384m 偏紧）+ server 模式内存泄漏 [#752](https://github.com/danielgatis/rembg/issues/752)（未修复）。直连只需 3 个包（RSS 估 120-200MB），u2netp 张量规格可从 rembg `sessions/base.py::normalize` + `sessions/u2netp.py` 逐行移植，结果与 rembg u2netp 一致。代价：失去 alpha_matting/decontaminate（恰是重依赖来源，u2netp 场景用不上）；L2 换模型（isnet 系同规格）同样直连，不受影响。备选 rembg[cpu]==2.0.81 + `new_session("u2netp")` + mem_limit 对冲——已被否。
2. **✓ 部署不加 compose**。现状：CI `docker save rt:latest | gzip` → scp `app.tar.gz` → ssh `docker load` + 裸 `docker run -d --name rt_app -p 81:80`（无 network/卷/env）。v1 改动范围表里"docker-compose 两服务"与现实不符。修正：第二镜像 `rt-ai:latest` 同管道部署；`docker network create rt-net || true` 幂等建网；sidecar 不映射宿主端口，仅内网 `http://rt-island-cut-ai:8100`；rt_app 挂网 + 注入 `ISLAND_CUT_AI_URL`。compose 重构留作独立议题。
3. **✓ matte_client 用 sync `httpx.Client`**（v1 骨架是 async def）。理由：`create_job` 是 sync def 端点（CPU 密集走线程池是既有模式），async 化会迫使 run_cut 上事件循环或加 to_thread，复杂度不值；sync Client 在线程池里天然安全。httpx 已是 backend 依赖（pyproject）。
4. **模型构建期内嵌 + md5 校验**。URL：`https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx`（release tag 固定 v0.0.0，4,574,861 字节，md5 `8e83ca70e441ab06c318d82300c84806`）。GitHub Actions 构建机下载可达性无虞；不用 apt 装 curl（slim 自带 python，`urlretrieve` + hashlib 校验）。注意 rembg 2.0.78+ 模型目录布局已改为 `$REMBG_HOME/models/`（U2NET_HOME deprecated）——直连方案无关（自己管路径 `/models/u2netp.onnx`）。
5. **u2netp 推理规格（直连实现契约）**：输入 `(1,3,320,320)` float32 NCHW RGB——resize 320 LANCZOS → `/255` → `(x-mean)/std`（mean=(0.485,0.456,0.406)，std=(0.229,0.224,0.225)，ImageNet 统计）；输出 `(1,1,320,320)` → `out[0][0]` **逐图 min-max 归一** → ×255 uint8 → L PNG。输入张量名从 `session.get_inputs()[0].name` 动态取，不硬编码。`OMP_NUM_THREADS=1` 同时压 ORT intra/inter op 线程。
6. **ai 模式的 alpha 语义**：`fg = ai_mask > alpha_threshold`（严格大于，与 alpha 通路一致；上采样双线性/lanzcos 只在主体边界产生 1-2px 过渡环，远背景恒 0，默认阈值 0 不会全图变前景，过渡环并入主岛 = 软边保留）。裁剪时 `_crop_piece` ai 分支在 grow(island mask) 内写 **ai_mask 软值**（非二值），AI 软边不丢失——与 alpha 模式"保留原 AA 渐变"同构。整图透明底 `full[...,3] = ai_mask`（软 mask 核对用）。
7. **640px 长边重采样**（继承 v1 杠杆）：mask 是低频信息，对岛切下游无损；上传/推理/缓存体积都按 640 计。
8. **缓存位置与清理**（细化 v1 决策 4）：临时目录 `rt_island_cut_ai_cache`（可配 `island_cut_ai_cache_dir`），TTL 惰性清扫（默认 1440min，比 job 的 60min 长——缓存便宜且跨会话调参受益），机制复用 `IslandJobStore._prune` 模式。
9. **capabilities 端点**（v1 未提，本版新增）：`GET /api/island-cut/capabilities` → `{"ai_matting": bool(url 配置)}`，按配置判定不 ping sidecar——前端据此置灰 AI chip，避免用户打了才知道 503。
10. **✓ 不做本地起服务/本地 Docker 冒烟**：验证 = pytest 全绿 + pnpm build + CI 部署健康检查（deploy.yml 已有 rt_app 双检查，加 `docker exec rt_app curl -sf http://rt-island-cut-ai:8100/health`）；ai 实际效果/降级/缓存命中在服务器上人工验证。

## 五、接口 / 代码骨架

```python
# matte_client.py
MODEL = "u2netp"; LONG_EDGE = 640

class MatteClient:
    def __init__(self, base_url, timeout_sec, cache_dir, ttl_sec, clock=time.monotonic): ...
    def resample(self, data: bytes) -> tuple[bytes, int, int]: ...      # (small_png, w, h)
    def get_mask(self, data: bytes) -> bytes | None:                    # None = 上层降级
        key = f"{hashlib.sha256(data).hexdigest()}:{MODEL}:{LONG_EDGE}"
        ...  # 缓存命中 → 返回；miss → POST {base_url}/matte → 200 存缓存
    def upsample(self, mask_bytes: bytes, size: tuple[int, int]) -> np.ndarray: ...

# service.py
def run_cut(rgba, params, ai_mask: np.ndarray | None = None) -> CutResult:
    ...  # mode=="ai": fg = ai_mask > params.alpha_threshold（router 保证非空）

# router.py
@router.get("/capabilities")
def capabilities(matte = Depends(_matte_dep)): return {"ai_matting": matte is not None}

# sidecar server.py（直连推理，规格见决策 5）
@app.post("/matte")
def matte(body: bytes = Request.body...): ...   # raw bytes → mask PNG (L)

# config.py
island_cut_ai_url: str = ""            # 空 = AI 关闭，行为与现状一致
island_cut_ai_timeout_sec: float = 3.0
island_cut_ai_cache_dir: str = ""      # 空 → tempdir/rt_island_cut_ai_cache
island_cut_ai_cache_ttl_min: int = 1440
```

## 六、职责边界

- **matte_client**：只管「拿 mask」（重采样/缓存/超时/降级信号），不懂切割、不知岛。
- **service.py**：只管「拿到 mask 之后的一切」，不知 sidecar 存在（ai_mask 是普通 ndarray 参数）。
- **sidecar**：无状态纯推理，不存 job、不懂业务、不做岛切；挂了随时可重建（L4 云 API 未来同 seam 接入，换 URL 而已）。
- 防蔓延：sidecar 不引 rembg 全家桶、主服务不装 onnxruntime、不做增量重切、不做多用户隔离。

## 七、改动范围（影响面，现状列基于实际扫描）

| 模块 | 现状 | 改后 | 影响 |
| --- | --- | --- | --- |
| island_cut/service.py | run_cut 两通路（alpha/white） | +ai_mask 参数与 ai 分支 | 参数可选，向后兼容 |
| island_cut/schemas.py | mode 三值 | +“ai”、CutResponse+ai_fallback | 旧值不动 |
| island_cut/router.py | build_router(store_provider) | +matte_provider、ai 流程、/capabilities | provider 的 request 参数必须标 `Request` 注解（已踩坑） |
| matte_client.py | 不存在 | 新增（sync httpx.Client） | httpx 已在依赖 |
| core/config.py | 无 AI 配置 | +4 个 island_cut_ai_* 配置 | 缺省行为不变 |
| main.py lifespan | 建 store | +条件建 MatteClient | url 空则 None，零影响 |
| docker/ | 不存在（单镜像） | +island-cut-ai 目录（直连 sidecar） | 磁盘 +~250MB 估（slim+onnxruntime+模型 4.4MB） |
| deploy.yml | 单镜像 save/SCP/run | 第二镜像同管道 + rt-net + --memory 384m + env/健康检查 | SSH script 变长，模式不变 |
| .dockerignore | 缺 backend/.venv | +backend/.venv | 顺手修既有隐患 |
| 前端 island-cut | 三模式 chip | +AI chip（capabilities 置灰）+ ai_fallback 标签 | 纯增量 |

## 八、迁移 / 实施路径（实施计划已批准，暂停中，可随时续做）

1. 后端：config → matte_client → service ai 分支 → schemas → router → main；pytest 全绿（含降级/缓存/503 用例）
2. Sidecar：docker/island-cut-ai 三文件（Dockerfile 内嵌模型 + md5）
3. 部署：deploy.yml 双镜像 + rt-net + mem_limit + 健康检查；.dockerignore 补 backend/.venv
4. 前端：capabilities 探测 + AI chip + 降级标签；pnpm build
5. 收尾：rt-backend-extension skill 速查同步
- 回退：服务器 `docker stop rt-island-cut-ai` + rt_app 去掉 env = 回到 L0（ai_fallback 自动兜底，甚至不停 sidecar 也行）

## 九、验收标准

| # | 验证项 | 方法 |
| --- | ------ | ---- |
| 1 | 后端回归 + 新用例全绿 | `uv run pytest -q` |
| 2 | 前端构建 | `pnpm run build` |
| 3 | CI 部署成功，两容器健康检查过 | deploy.yml（含新增 sidecar exec curl） |
| 4 | ai 模式复杂背景照片出块结构合法 | 服务器 UI 人工验证 |
| 5 | sidecar stop 后 create_job 仍成功，ai_fallback=true | 服务器手测 |
| 6 | 同图二次请求不打 sidecar | 服务器日志 |
| 7 | sidecar RSS < 384m 不 OOM | `docker stats` 实测（假设 1 的最终检验） |
| 8 | url 为空时行为与现状逐字节一致 | 现有回归全绿 |

## 十、决策记录（本轮已拍板）与开放项

| # | 决策 | 结论 |
| --- | --- | --- |
| 1 | sidecar 实现 | ✓ 直连 onnxruntime（否决 rembg 包） |
| 2 | 部署形态 | ✓ 沿用现有 CI 裸 docker run + rt-net，不引 compose |
| 3 | 验证方式 | ✓ 不做本地起服务/Docker 冒烟，端到端交 CI 部署 |
| 4 | mem_limit | 384m（v1 推荐，未变） |

开放项：实施暂停中（用户指令"先暂停"，当前产出已够用）；续做时从 §八 路径第 1 步开始，实施计划底稿见会话计划文件（cheeky-doodling-simon），本设计文档已自包含其全部内容。

## 十一、参考

- 调研来源（2026-08 抓取）：[rembg pyproject.toml (main)](https://github.com/danielgatis/rembg/blob/main/pyproject.toml) · [bg.py 顶层 import](https://github.com/danielgatis/rembg/blob/main/rembg/bg.py) · [sessions/u2netp.py](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py) · [sessions/base.py normalize](https://github.com/danielgatis/rembg/blob/main/rembg/sessions/base.py) · [release v0.0.0 模型资产](https://github.com/danielgatis/rembg/releases/tag/v0.0.0) · [issue #752 内存泄漏](https://github.com/danielgatis/rembg/issues/752) · [pymatting 1.1.15 依赖](https://pypi.org/pypi/pymatting/json) · [ORT 内存调优](https://onnxruntime.ai/docs/performance/tune-performance/memory) · [U-2-Net-ONNX-Sample（直连交叉印证）](https://github.com/Kazuhito00/U-2-Net-ONNX-Sample/blob/main/sample_u2net_onnx.py)
- 代码：backend/src/rt_backend/island_cut/service.py:161-201（run_cut fg 分支接入点）、:139-158（_crop_piece）、router.py（provider 注解坑）、store.py:69-75（_prune 模式）
- 本主题文档：v1 设计 · compare_matting-libraries v1 · island-cut-params v1 concepts · interior-white-region v2
