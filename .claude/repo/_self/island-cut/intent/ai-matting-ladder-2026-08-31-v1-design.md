# Intent: AI 抠图升级阶梯（L0→L4）预测设计（v1）

> **Date:** 2026-08-31
> **Topic:** island-cut
> **类型:** intent doc（预测设计）
> **版本:** v1（首版；与 interior-white-region v2 并列的新设计想法，可互相引用）
> **状态:** 试验
> **核心问题:** 在 2C2G/Docker/主服务 ≤300MB 的硬约束下，为 island_cut 设计一条可逐级升级、每级可独立回退的 AI 抠图路径。

相关文档：[../project/compare_matting-libraries-2026-08-31-v1-status.md](../project/compare_matting-libraries-2026-08-31-v1-status.md)（可行性判定依据）· [interior-white-region-2026-08-31-v2-design.md](./interior-white-region-2026-08-31-v2-design.md)（下游功能，与本设计正交且可组合）

## 本版要验证的假设

1. `run_cut` 下游（closing → label → 岛切 → 白区）只消费 fg mask，不关心来源——AI 接入 = 换 fg 来源，下游零改动。依据：service.py:161-201 中 fg 仅在 167-171 行产生，其后全部与来源无关。
2. u2netp（4.7MB）推理峰值在 384m mem_limit 的独立容器内可稳定运行不 OOM（compare 文档估 ~100-250MB，待实测）。
3. 主服务通过 httpx 调 sidecar（超时 3s）+ 降级回退，故障面不扩大：sidecar 全挂时主服务行为等同现状。

## 一、设计原则

| # | 原则            | 体现                                                                                             |
| - | --------------- | ------------------------------------------------------------------------------------------------ |
| 1 | mask 来源可插拔 | AI 只是新增一种 fg 来源（mode="ai"），下游岛切/白区全复用                                        |
| 2 | OOM 隔离        | AI 永远跑独立 sidecar 容器、独立 mem_limit；主服务 300MB 预算不动                                |
| 3 | 降级而非失败    | sidecar 超时/5xx → 自动回退 L0（white/alpha 模式）+ 响应标注                                    |
| 4 | 模型进镜像      | 模型 COPY 进 Docker 镜像，不依赖运行时从 GitHub 下载（国内不可靠）                               |
| 5 | 缓存优先        | sha256(图片字节)+model 为键缓存 mask；单人反复调试命中率高                                       |
| 6 | 阶梯独立回退    | 每一级部署后可单独下线回退到上一级，互不锁死                                                     |
| 7 | License 底线    | RMBG 系（BRIA）为非商用授权，商用场景整体排除；BiRefNet(MIT)/U²-Net(Apache-2.0)/rembg(MIT) 可用 |

## 二、阶梯定义

| 级                   | 触发条件                                                             | 代表库/模型                                                                                                              | 内存档        | 部署形态                                            |
| -------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------- | --------------------------------------------------- |
| L0（现状）           | 白底/透明底                                                          | scipy 栈                                                                                                                 | 几十 MB       | 主服务内                                            |
| L1 预算内在线 AI     | 偶发复杂背景                                                         | rembg + u2netp（4.7MB）                                                                                                  | 估 ~100-250MB | sidecar，mem_limit 384m                             |
| L2 放宽 sidecar 预算 | 复杂背景常态化；动漫素材优先试 isnet-anime（rembg 自带会话，~170MB） | rembg + u2net / isnet-general-use / silueta；量化版可将 L2 拉回 L1 资源档                                                | 估 ~400-700MB | 同 sidecar，mem_limit 768m-1g（2GB 总量单人可分配） |
| L3 离线预生成        | 顶级质量、不占服务器                                                 | BiRefNet（rembg birefnet-* 系列，MIT；general-lite 体积较小）、transparent-background(InSPyreNet)；RMBG-1.4/2.0 商用排除 | 不占服务器    | 本机跑模型 → 结果 PNG 上传，服务器只发缓存         |
| L4 云 API 兜底       | 一张不想算                                                           | remove.bg；阿里云/腾讯云抠图 API（国内计费按张，无模型问题）                                                             | 0             | 纯 HTTP                                             |

**阶梯内杠杆**（不占新等级）：

- int8 量化：`onnxruntime.quantization.quantize_dynamic`，u2net ~168MB → ~45MB 估，质量略降。
- 输入限边长：推理前长边压至 640px，mask 上采样回原尺寸——mask 是低频信息，对岛切下游无损。

## 三、模块拆分

```
backend/
├── src/rt_backend/island_cut/
│   ├── service.py        # mode 增 "ai"：fg = 远端 mask 阈值化；167-171 行增一分支，下游不动
│   ├── matte_client.py   # 新：sidecar httpx 客户端 + sha256 缓存 + 超时降级
│   ├── router.py         # create_job 接受 mode="ai"；降级时响应标注
│   └── schemas.py        # mode Literal 增 "ai"；响应 mode 可能带 _fallback 后缀
├── src/rt_backend/core/config.py   # + ISLAND_CUT_AI_URL（sidecar 地址，缺省空 = 关闭 AI）
docker/island-cut-ai/
├── Dockerfile            # slim + onnxruntime + rembg；模型 COPY 进镜像
├── server.py             # POST /matte (multipart) → alpha mask PNG；无状态
└── models/               # u2netp.onnx（L1）；L2 换大模型仅改此目录
nginx.conf                # 不改：backend 内部代理 sidecar
tests/test_matte_client.py # 新：降级/缓存/超时用例（mock httpx）
```

## 四、数据流（关键场景）

**场景 A：AI 切分（L1 上线后）**

上传 → router.create_job（mode="ai" 且 config 启用）→ matte_client：
cache 查 `sha256(bytes)+model` → miss → POST sidecar /matte（长边 ≤640px 重采样后上传）→ 返回 mask PNG → 上采样回原尺寸 → 存 job 目录并写缓存 → `fg = mask >= alpha_threshold` → 既有 closing/label/岛切/白区检测 → 响应 `mode="ai"`。

**场景 B：降级**

sidecar 超时(3s)/5xx/连接拒绝 → log warning → 以原 bytes 走既有 auto 判定重跑 → 响应 `mode="white"` 或 `"alpha"`，另附 `ai_fallback: true` 字段 → 用户可感知但服务不失败。

**场景 C：L3 离线预生成（无 sidecar 依赖）**

本机跑 BiRefNet 生成透明底 PNG → 走现有 alpha 模式上传——L3 对服务器是零改动，天然成立。

## 五、接口 / 代码骨架

```python
# matte_client.py 骨架
async def get_mask(data: bytes, model: str, base_url: str) -> bytes | None:
    key = hashlib.sha256(data).hexdigest() + ":" + model
    if hit := cache_dir / f"{key}.png": ...
    try:
        r = await http.post(f"{base_url}/matte", files={"file": data}, timeout=3.0)
    except (httpx.TimeoutException, httpx.HTTPError):
        return None                      # 上层降级
    ...

# sidecar server.py 骨架（FastAPI，无状态）
@app.post("/matte")
def matte(file: bytes = File(...)):
    rgba = load_rgba(file)                       # 复用同一加载逻辑
    mask = session.predict(rgba)                 # rembg session
    return PNG(mask)                             # 单通道 alpha

# config.py
island_cut_ai_url: str = ""    # 空 = AI 关闭，行为与现状完全一致
```

## 六、职责边界

- **matte_client**：只管「拿 mask」（缓存/超时/降级），不懂切割。
- **service.py**：只管「拿到 mask 之后的一切」，不知 sidecar 存在。
- **sidecar**：无状态纯推理服务，不存 job、不懂业务；挂了随时可重建。
- 防蔓延：sidecar 不做岛切；主服务不装 onnxruntime；L4 云 API 也从 matte_client 同一 seam 接入（换 URL 与鉴权而已）。

## 七、改动范围（影响面）

| 模块               | 现状                     | 改后                             | 影响                                       |
| ------------------ | ------------------------ | -------------------------------- | ------------------------------------------ |
| service.py:167-171 | fg 两分支（alpha/white） | +ai 分支（远端 mask 阈值化）     | 参数可选，向后兼容                         |
| matte_client.py    | 不存在                   | 新增                             | 新文件                                     |
| config.py          | 无 AI 配置               | +island_cut_ai_url               | 缺省空，行为不变                           |
| schemas.py:12      | mode 三值                | Literal 增 "ai"                  | 旧值不动                                   |
| docker/            | 仅主服务镜像             | +island-cut-ai 镜像              | 磁盘 +~650MB 估（onnxruntime+依赖链+模型） |
| docker-compose     | 两服务（nginx+backend）  | +island-cut-ai（mem_limit 384m） | 主服务预算不变                             |
| 主服务依赖         | 无 onnx/torch            | **不增**                   | 300MB 预算不破                             |

## 八、迁移 / 实施路径（阶梯即路径）

- **L1**：sidecar(u2netp, 384m) + matte_client + config 开关。验收后即为默认 AI 档。
- **L2**：换/加模型进 sidecar models/ 目录，调 mem_limit。代码零改动（原则 1 的红利）。
- **L3**：离线脚本（本机）+ 结果走 alpha 模式，服务器零改动。
- **L4**：matte_client 指向云 API（同 seam），按张付费。
- 每级独立上线、独立回退：下线 sidecar 容器 = 回到 L0。

## 九、验收标准

| # | 验证项                                                                      | 方法                                     |
| - | --------------------------------------------------------------------------- | ---------------------------------------- |
| 1 | L1 sidecar 在 mem_limit 384m 下跑 20 张真实素材无 OOM，P95 < 3s             | docker stats + 计时                      |
| 2 | 降级：docker stop sidecar 后 create_job 仍成功返回，响应带 ai_fallback=true | 手测/mock 单测                           |
| 3 | 缓存命中：同图二次请求不触 sidecar，<50ms                                   | 日志 + 计时                              |
| 4 | 主服务 RSS 在 AI 模式下仍 < 300MB                                           | 容器内实测                               |
| 5 | island_cut_ai_url 为空时行为与现状逐字节一致                                | 现有回归全绿                             |
| 6 | AI mask 下游兼容：ai 模式产出的岛切/白区结果结构合法                        | 复用 interior-white-region 验收 1/2 用例 |
| 7 | sidecar 镜像离线可构建（无运行时模型下载）                                  | 断网构建验证                             |

## 十、待用户拍板的决策

| # | 决策                                         | 推荐                                                        |
| - | -------------------------------------------- | ----------------------------------------------------------- |
| 1 | 首级选哪级                                   | L1（链路价值最大，验证假设 1-3）                            |
| 2 | sidecar mem_limit 初值                       | 384m（u2netp 估峰值上限之上留余量）                         |
| 3 | ai 模式参数暴露程度                          | 一期固定 u2netp + 默认阈值；schemas 预留 model 字段不实现   |
| 4 | 缓存位置与清理                               | 全局缓存目录 + 复用 job TTL 思路做惰性清理                  |
| 5 | 降级标注方式                                 | 响应加 ai_fallback 布尔字段（比 mode 后缀更显式）           |
| 6 | 素材以动漫封面为主时是否直跳 isnet-anime(L2) | 先 L1 验证链路，跑通后用同一批素材对比 isnet-anime 再定跳级 |
| 7 | License 底线确认                             | 个人非商用全可用；若未来商用，排除 RMBG 系                  |

## 十一、参考

- 代码：backend/src/rt_backend/island_cut/service.py:167-171（fg 分支，唯一接入点）、config.py、nginx.conf、backend/pyproject.toml:12（httpx 已是依赖）
- 本主题文档：project/compare_matting-libraries-2026-08-31-v1-status.md（各级可行性判定）· intent/interior-white-region-2026-08-31-v2-design.md（下游白区功能）
- 模型资料：rembg 官方 sessions 列表（u2netp/silueta/isnet-*/birefnet-*）、BiRefNet(MIT)、transparent-background、RMBG(BRIA 非商用) 发布页
