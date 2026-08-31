# Intent: 内部白区「检测→编号→勾选重切」预测设计（v2）

> **Date:** 2026-08-31
> **Topic:** island-cut
> **类型:** intent doc（预测设计）
> **版本:** v2（相对 v1：新增「单人使用」约束——apply 覆盖同 job 理由强化；MAX_PIXELS 决策从防御值改为按实际素材定；新增 TTL 放宽决策点；并发防御明确从简。v1 结论均保留，无推翻）
> **状态:** 候选
> **核心问题:** 在不加依赖、≤300MB 内存预算内，把主体内部白色区域变成「可识别、可编号、可勾选转透明」的一等公民。

相关文档：[interior-white-region-2026-08-31-intent.md](./interior-white-region-2026-08-31-intent.md) · [v1 设计](./interior-white-region-2026-08-31-v1-design.md) · [../project/compare_matting-libraries-2026-08-31-v1-status.md](../project/compare_matting-libraries-2026-08-31-v1-status.md)

## 本版要验证的假设

1. 内部白区 = `is_white & ~flood_fill_background(is_white)` 的连通域——现有泛洪语义取补集即可直接求得，无需新算法。
2. 勾选重切可通过「从 fg 中扣除所选洞的 mask，再走既有 closing/label/crop 流程」实现，核心算法结构不变。
3. 典型尺寸（≤4MP）下新增计算的内存增量为图像缓冲级（几十 MB 内），300MB 预算可容纳。
4. （v2 新增）单机单人串行使用下，store 既有 `threading.Lock` 已覆盖全部并发面，无需额外同步机制。

## 一、设计原则

| # | 原则 | 体现 |
| - | --- | --- |
| 1 | 零新依赖 | 只用现有 scipy.ndimage/numpy/PIL 原语，不引 cv2/skimage/AI 库 |
| 2 | 默认行为不变 | 不勾选任何洞时输出与现状一致，纯加法演进 |
| 3 | 参数可关 | `hole_min_area=0` 关闭检测，老调用方零感知 |
| 4 | 磁盘换内存 | 原图字节落 job 目录（TTL 一致清理），而非驻留内存 |
| 5 | 先简后优 | apply 全量重切，不做增量岛级重算（二期再议） |
| 6 | 单机单人从简 | 不引入任务队列/限流/请求级互斥；store 既有锁已够 |

## 二、模块拆分

```
backend/src/rt_backend/island_cut/
├── service.py   # + detect_holes()：补集连通域检测 + 阅读序编号
│                #   run_cut() 增可选 exclude_mask 参数（扣除勾选洞后重切）
├── schemas.py   # + HoleInfo、ApplyRequest；CutResponse 增 holes 字段
├── router.py    # + POST /jobs/{id}/apply；create_job 落原图副本
└── store.py     # Job 增 holes 元数据与原图路径；apply 时替换 pieces/holes
```

不新增文件级模块——改动全部落在既有四个文件的职责边界内。

## 三、数据流（关键场景）

**场景 1：上传 → 切割 → 洞列表**

上传 → router.create_job（校验 50MB/像素上限，router.py:40-80）→ load_rgba → run_cut：
white 模式下 `is_white = np.all(rgba[...,:3] >= bg_threshold, axis=2)` → `flood_bg = flood_fill_background(is_white)` → `interior = is_white & ~flood_bg` → `ndimage.label(interior)` → 过滤 `area >= hole_min_area` → `_order_reading` 排序编号 `hole_00…` → pieces 与 holes 元数据入 store → 响应含 `holes: [HoleInfo]`。

**场景 2：勾选 → apply 重切**

POST apply(hole_ids) → store 取原图字节（场景 1 落盘的副本）→ 重新 load + 重跑 run_cut，fg 扣除勾选洞的 union mask → 覆盖 job 的 pieces/holes → 返回与 create 同构的 CutResponse。每次 apply 从原图出发 → 接口幂等，可撤销（改勾选集合再 apply 即可）。单人串行使用下不存在 apply 与 apply/create 的竞争窗口。

## 四、关键决策（含选型说明）

1. **检测 = scipy 连通域补集**。理由：零依赖、语义已在 `flood_fill_background`（service.py:59-64）就位、毫秒级、内存为 bool 数组级。备选 cv2 `findContours RETR_CCOMP`：功能等价但 +120~160MB 磁盘且与现有栈重叠。备选 AI（rembg）：显著性模型填洞，恰与本需求冲突，且全尺寸模型超 300MB 预算（见 compare 文档主表）。
2. **一期仅 white 模式**。理由：alpha 模式内部洞本就保留原 alpha 透明（service.py:152-155），无此需求。
3. **洞默认保留白，勾选才透明**。理由：不改变现状输出（原则 2）；备选「默认全透明」会破坏向后兼容。
4. **原图字节落盘换可重切性**。理由：store 现不存原图（store.py:36-52，compare 差距 5）；单人使用虽无并发叠加，但驻留内存的算术不变——12MP RGBA ≈ 48MB/job 常驻，两三个未过期 job 即 ~150MB，足以顶破 300MB；落盘与 TTL 清理天然对齐，成本可忽略。备选存 fg mask 的 .npy：读取快但体积更大，一期不取。
5. **apply = 全量重切 + 幂等 + 覆盖同 job**。理由：复用既有流程正确性，实现最小；单人使用下无请求交错，覆盖同 job（pieces/holes 全量替换、URL 不变）没有竞争风险，前端刷新即可见。增量重切（只重算受影响岛）留二期。
6. **洞编号复用 `_order_reading` 阅读序**。理由：与岛屿编号（island_NN）体验一致。
7. **MAX_PIXELS 按实际素材定，而非防御值**。理由：单机自用下 40MP 的防滥用意义消失；上限唯一作用变成保护 300MB 容器不被自己手滑的大图 OOM。推荐按个人素材最大尺寸的 2~3 倍取值（12MP 对 4000×3000 已宽裕）；若现有素材从未超 ~4MP，甚至可更低。此项涉及行为变化，列入待拍板。
8. **不引入 AI 抠图库（远期备注）**：若未来复杂背景成为真实输入，compare 文档结论下唯一预算内路径为 rembg+u2netp 独立容器（单独 mem_limit、模型 COPY 进镜像）或离线预生成；单人使用下负载极低，两条路径的可行性都进一步上升，但均为独立议题，不混入本期。
9. **TTL 可放宽（v2 新增）**。现状 3600s（store.py:28）按公共服务活跃度设计；单人 job 量少、磁盘占用可控，放宽至 12~24h 可让「切完 → 看洞 → 勾选 → apply」跨天完成。列入待拍板。

## 五、接口 / 代码骨架

```python
# schemas.py 新增
class HoleInfo(BaseModel):
    id: str                    # hole_00, hole_01 …（阅读序）
    x: int; y: int; width: int; height: int
    area: int

class ApplyRequest(BaseModel):
    hole_ids: list[str]        # 全量勾选集合（幂等，非增量切换）

# CutResponse 增字段
holes: list[HoleInfo] = []

# router.py 新增
POST /api/island-cut/jobs/{job_id}/apply   # body: ApplyRequest → CutResponse
```

```python
# service.py 骨架
def detect_holes(is_white, flood_bg, hole_min_area, structure) -> list[dict]:
    interior = is_white & ~flood_bg
    lbl, n = ndimage.label(interior, structure=structure)
    # 逐域统计 area/bbox，过滤 hole_min_area，_order_reading 编号

def run_cut(rgba, params, exclude_mask: np.ndarray | None = None):
    # fg 计算后：if exclude_mask is not None: fg &= ~exclude_mask
    # 其余 closing/label/crop 流程不变
```

## 六、职责边界

- **service.py**：纯算法（检测、重切），不知 HTTP 与持久化。
- **router.py**：校验、编排、错误码、落原图副本的触发。
- **store.py**：持久化与 TTL（pieces/holes 元数据/原图），apply 时替换 job 内容。
- **schemas.py**：IO 契约唯一来源。
- 防蔓延：不做洞的交互式编辑器逻辑、不做增量重切、不做 AI 检测路径、不做多用户隔离——均为二期/独立议题。

## 七、改动范围（影响面）

| 模块 | 现状 | 改后 | 影响 |
| --- | --- | --- | --- |
| service.py:161-201 | run_cut(fg→closing→label→crop) | +exclude_mask 参数、+detect_holes | 向后兼容（参数可选） |
| schemas.py:32-41 | CutResponse 无 holes | +holes 字段、+2 model | 响应加字段，旧字段不动 |
| router.py:40-80 | create 不落原图 | +落原图副本；+apply 端点 | 磁盘占用 +原图大小/job（TTL 内） |
| store.py:28 | ttl_sec=3600 | 可配置放宽（待拍板） | 参数化改动，默认值待定 |
| store.py:36-52 | 不存原图、无 holes | Job 增原图路径与 holes；apply 替换 | 结构变化限于 store 内部 |
| tests/test_island_cut.py | 现有回归 | +洞检测/apply 用例 | 纯新增 |

## 八、迁移 / 实施路径

- **M1 检测+暴露**：detect_holes + CutResponse.holes + 落原图。纯只读增强，可独立验收（不 apply 时输出与现状一致）。
- **M2 apply 重切**：apply 端点 + store 替换逻辑。
- **M3（可选）**：MAX_PIXELS 按素材定值 + TTL 放宽 + 前端序号勾选交互（前端另行仓库/实施）。

## 九、验收标准

| # | 验证项 | 方法 |
| --- | --- | --- |
| 1 | 环形/含内白测试图：洞数量、编号、bbox、面积正确 | 新增单测 |
| 2 | 与边界连通的白色不被误判为洞 | 泛洪语义单测（构造贴边白块） |
| 3 | apply 勾选后对应区域 alpha=0，未勾选保留白色 | 单测 + 手验输出 PNG |
| 4 | 未勾选/不调用 apply 时输出与现状一致 | 现有 tests/test_island_cut.py 全绿回归 |
| 5 | 4MP 输入全流程峰值 RSS < 300MB（单人串行场景） | 容器内实测（/usr/bin/time -v 或 docker stats） |
| 6 | holes 为空时响应与旧版结构兼容 | 单测字段快照 |

## 十、待用户拍板的决策

| # | 决策 | 推荐 |
| --- | --- | --- |
| 1 | apply 结果覆盖同 job_id 还是生成新 job | 覆盖同 job（单人无竞争，URL 不变，刷新即可见） |
| 2 | apply 语义：全量勾选幂等 vs 增量切换 | 全量幂等（可撤销，实现简单） |
| 3 | hole_min_area 默认值 | 200px（可调，0 关闭检测） |
| 4 | MAX_PIXELS 取值 | 按个人素材最大尺寸的 2~3 倍定；素材普遍 ≤4MP 时取 12MP 仍宽裕 |
| 5 | bg_threshold 复用现状 235 还是洞单独阈值 | 复用 235（一期不加新阈值） |
| 6 | TTL 是否放宽 | 12h（单人 job 量少，apply 窗口跨天更从容） |

## 十一、参考

- 代码：backend/src/rt_backend/island_cut/service.py:59-64（泛洪）、:161-201（run_cut）、router.py:24-25（上限）、router.py:94-105（内存 zip）、store.py:28（TTL）、store.py:36-52（不落原图）
- 本主题文档：intent/interior-white-region-2026-08-31-intent.md · intent/interior-white-region-2026-08-31-v1-design.md（v1 保留） · project/compare_matting-libraries-2026-08-31-v1-status.md
- 现有测试：backend/tests/test_island_cut.py
