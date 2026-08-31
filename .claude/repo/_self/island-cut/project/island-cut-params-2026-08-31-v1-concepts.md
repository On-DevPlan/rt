# island-cut-params 概念阐述（2026-08-31 v1）

> **Topic:** island-cut
> **类型:** project doc（模块概念阐述）
> **版本:** v1（首版）
> **范围:** island_cut 模块的**参数系统**——8 个参数的含义、各自驱动的算法函数、参数表达不到的固定策略、与参考实现（`a_dart/prj/fr/.tool/chess-piece-extract/scripts/` 三脚本）参数空间的对照现状
> **关联:** [compare_matting-libraries-2026-08-31-v1-status.md](./compare_matting-libraries-2026-08-31-v1-status.md) · [../intent/interior-white-region-2026-08-31-v2-design.md](../intent/interior-white-region-2026-08-31-v2-design.md)

## 1. 整体框架

参数系统 = **一条五段流水线上的 8 个旋钮**。`CutParams`（schemas.py 与 service.py:29 双定义，字段一致）从 HTTP `params` JSON 一路传到 `run_cut`（service.py:161），8 个参数分别作用在流水线的不同段，互不越界：

```
源图(bytes)
  │
  ▼
① 前景判定 ────── mode 选通路
  │   alpha 通路: fg = alpha > alpha_threshold          [alpha_threshold]
  │   white 通路: fg = ~flood_fill_background(rgb≥t)    [bg_threshold]
  │   auto: detect_mode 按"是否存在 alpha<10 像素"二选一  [mode]
  ▼
② 形态学闭运算 ── fg 桥接细小断裂                        [closing_iters，0=关]
  ▼
③ 连通域标记 ──── ndimage.label(structure=…)            [connectivity 4/8]
  ▼
④ 岛筛选 + 细节归属
  │   area ≥ min_area                    → 主岛          [min_area]
  │   small_min_area ≤ area < min_area   → smalls，归入外扩 pad 内包含它的最近主岛
  │                                                        [small_min_area, padding(归属窗语义)]
  │   其余                               → 噪点丢弃
  ▼
⑤ 裁剪 + alpha 写入 ── bbox 外扩 pad 裁剪                [padding(留白语义)]
  │   alpha 模式: 保留原 alpha（mask 外扩 1px 内）→ AA 渐变边缘（固定策略）
  │   white 模式: mask 内 255 / 外 0（二值，固定策略）
  ▼
pieces(island_NN.png) + 00_full_transparent.png → IslandJobStore(TTL)
```

概念分四组：**通路选择**（mode 及两条通路的阈值）、**形态参数**（closing_iters）、**岛屿结构参数**（min_area / small_min_area / padding / connectivity）、**固定策略**（写死在代码里、参数不可达的启发式）。

## 2. L1 概念名称表

模型级概念（脱离具体界面成立）。参数名以代码字段名为准，括号内为前端 label 原名。

| 概念名 | 一句话定义 | 首次提出语境 | 与其他概念的关系 |
| --- | --- | --- | --- |
| CutParams | 前后端共享的 8 字段参数契约 | 模块实现（schemas.py:8 / service.py:29） | 由 router 解析 JSON 后传给 run_cut |
| mode（模式） | 前景判定通路选择：auto/alpha/white | 模块实现；参考 v5/v9 两脚本的通用化 | 决定 alpha_threshold 与 bg_threshold 谁生效 |
| alpha 通路 | 透明底源图的前景判定：`fg = alpha > t` | 参考 extract_islands.py v5 | mode=alpha 或 auto 判定为透明底时启用 |
| white 通路 | 白底源图的前景判定：泛洪背景取补集 | 参考 extract.py v9 | mode=white 或 auto 判定为不透明时启用 |
| alpha_threshold（Alpha 阈值） | alpha 通路的前景 alpha 下限 | v5 的 `--alpha-threshold` | 仅 alpha 通路生效；调高可切断半透明粘连 |
| bg_threshold（白底阈值） | white 通路的白色判定下限 | v9 的 `--white-threshold` | 仅 white 通路生效；泛洪种子集的阈值 |
| 泛洪背景（flood bg） | 与图像边缘连通的白色区域 = 背景 | `flood_fill_background`（service.py:59） | white 通路的背景；被前景环绕的白**不是**背景 |
| closing_iters（闭运算） | binary_closing 迭代数 = 桥接断裂半径 | v5 的 `--closing-iters` / `--no-closing` | 作用于两种通路的 fg；0 = 关闭 |
| connectivity（连通域） | 连通域判定拓扑：4/8 邻域 | `ndimage.label` 的 structure 参数（service.py:67） | 影响所有连通域计算（岛、归属、泛洪） |
| min_area（最小面积） | 主岛面积下限，低于则不成为独立岛 | v5/v9 的 `--min-area` | 与 small_min_area 共同划分 岛/smalls/噪点 |
| smalls（小连通域） | 面积 ≥ small_min_area 但 < min_area 的域 | v9 的 SMALL_MIN_AREA 机制 | 归属（收养）到外扩 pad 内包含它的最近主岛 |
| padding（留白） | bbox 外扩像素；**一参两用**：裁剪留白 + 归属判定窗 | v9 的 `--padding`（v5 中为常量 20） | 同时是 `_crop_piece` 的外扩和 `_label_islands` 的归属窗 |
| 岛屿（主岛） | area ≥ min_area 的连通域，输出为一张切片 | 参考脚本 "island" 概念 | 按**阅读序**编号为 island_NN |
| 阅读序 | 行聚类（容差 max(24, 岛高×0.6)，固定策略）后行内按 cx 升序 | `_order_reading`（service.py:118） | 决定 island_NN / hole_NN 编号顺序（v2 设计复用） |
| piece（切片/块） | 单个岛的输出 PNG：bbox+pad 画布、mask 决定 alpha | router/store 的 `pieces` | job.pieces 元数据 + pieces/{filename} 端点 |
| job | 一次切割任务：临时目录 + 元数据 + TTL | IslandJobStore（store.py） | pieces 与 full.png 的持久化容器，默认 60min 过期 |
| 整图透明底（full.png） | 全图按 fg 写 alpha 的核对用输出 | 参考脚本 00_full_transparent.png | 固定名 `00_full_transparent.png`，随 ZIP 打包 |
| 固定策略 | 写死在代码、参数不可达的启发式集合 | 本轮讨论命名 | 行聚类容差 / AA 外扩 1px / white 模式二值 alpha / island_NN 命名（见 §5） |

## 3. 指称映射表（用户怎么说话 → 指什么）

| 用户以后说 | 实际指 | 别再用的模糊说法 |
| --- | --- | --- |
| "自动" | mode=auto：按是否存在 alpha<10 像素选通路 | "智能模式" |
| "白底阈值" | bg_threshold，**仅 white 通路生效** | "那个 235" |
| "Alpha 阈值" | alpha_threshold，**仅 alpha 通路生效** | "前景阈值"（不指明通路） |
| "闭运算" | closing_iters（0 = 关闭） | "平滑"、"抗锯齿" |
| "留白" | padding——注意**同时**是归属判定窗 | "边距" |
| "细节归属" | small_min_area（smalls 收养机制的总开关，0=关） | "噪点过滤"（那是 min_area 的事） |
| "最小面积" | min_area：主岛/非主岛分界 | "噪点阈值" |
| "连通域" | connectivity（4/8 邻域结构元） | "合并模式" |
| "内部亮区/内部白区" | 已知缺口：white 通路中被环绕白区当前一律保留；承接方案见 interior-white-region v2 设计（候选） | "挖空功能"（尚未实现） |
| "参数表达不到的部分" | §5 固定策略与未命名实体 | "隐藏参数" |

## 4. L2 布局内部模块指称表（按视图分组）

### IslandCutPage（前端 `/island-cut/studio`，类名出自 IslandCutPage.module.css）

| 模块名 | 是什么 | 父子关系 |
| --- | --- | --- |
| dropzone | 上传拖放区（点击/拖入选图） | panel > dropzone > preview |
| preview | 源图预览（衬 checker 棋盘格显示透明） | dropzone > preview |
| paramRow | 单个参数行：label + range 滑杆 + number 数字框 | paramList > paramRow |
| chip | 模式（自动/透明底/白底）与连通域（4/8 邻域）的切换按钮 | modeRow > chip |
| pieceGrid / pieceCard | 结果网格与单块卡片（checker 衬底 + 文件名 + 尺寸/面积） | panel > pieceGrid > pieceCard |
| spring | 结果工具栏里的弹性占位（把 ZIP 按钮推到右侧） | toolbar > spring |

### 后端目录（island_cut/ 四文件职责，类名/函数名为代码原名）

| 模块名 | 是什么 | 父子关系 |
| --- | --- | --- |
| schemas | CutParams / CutResponse / PieceInfo——IO 契约唯一来源 | — |
| service | 纯算法：run_cut 五段流水线，无 HTTP 无持久化 | run_cut → detect_mode / flood_fill_background / _label_islands / _order_reading / _crop_piece |
| store | IslandJobStore：内存注册表 + 临时目录 + TTL 惰性清扫 | Job{dir, pieces, created} |
| router | build_router(store_provider)：端点、校验（50MB/16M px）、zip 打包 | 依赖 provider 读 app.state.island_store |

## 5. 未命名实体与表达缺口（现状记录，非建议）

**固定策略（参数不可达，代码内常量）：**

| 描述 | 位置 | 当前值 | 建议命名（若参数化） |
| --- | --- | --- | --- |
| 阅读序行聚类容差 | `_order_reading` service.py:124 | max(24, 岛高×0.6) | row-tol |
| alpha 模式 AA 边缘外扩 | `_crop_piece` service.py:154 | dilation 1px | alpha-grow |
| white 模式 alpha 写入方式 | service.py:157 | 二值 255/0，无羽化 | alpha-feather |
| 输出命名 | run_cut | 固定 island_NN | naming 策略（v5 曾有 rowcol/reading 两档） |

**参考实现有、本项目参数空间无（v11 `extract_ui.py` 与 v9 缺口，截至本文档均无承接 intent）：**

| 缺口 | 参考参数 | 作用 | 现状 |
| --- | --- | --- | --- |
| 区域过滤 | `--max-bottom-y`（v9/v11） | y≥N 的岛丢弃（原为滤水印） | 无对应参数、无 intent |
| 双阈值分流 | `--dark-mean`、`--light-bg-threshold`（v11） | 按棋身均色分流，浅色主体用高阈值二次泛洪 | 无对应参数、无 intent |
| 挖内部亮区 | `--bright-threshold`、`--hole-min`（v11） | 被完全包围的亮区挖空 | **有承接**：interior-white-region v2 设计（候选，交互式勾选方案，非自动 punch） |
| 外描边包裹 | `--outline-px` + OUTLINE_COLOR（v11） | 沿外边界画描边防浅色主体被误删 | 无对应参数、无 intent |
| 填闭环小孔 | `--fill-tiny-holes`（v11） | 清理描边闭环残留 speck | 无对应参数、无 intent |

**表达力现状结论（对照参考三脚本）：** 对 v5（alpha 源）为完整超集；对 v9（白底通用）缺 `max-bottom-y` 一项；对 v11（UI 特化）为明显子集（上表 5 项中 4 项无承接）。参数隐式交互一处：padding 同时控制裁剪留白与归属窗，调参时二者联动。

## 6. 参考

- 代码：backend/src/rt_backend/island_cut/service.py:29（CutParams）、:54（detect_mode）、:59（泛洪）、:67（structure）、:78（_label_islands）、:118（_order_reading）、:139（_crop_piece）、:161（run_cut）；schemas.py:8-17；router.py:24-28（上限）；store.py（TTL）
- 参考实现：`D:\code\a_dart\prj\fr\.tool\chess-piece-extract\scripts\{extract_islands,extract,extract_ui}.py`
- 本主题文档：compare_matting-libraries-2026-08-31-v1-status.md · ../intent/interior-white-region-2026-08-31-{intent,v1-design,v2-design}.md
