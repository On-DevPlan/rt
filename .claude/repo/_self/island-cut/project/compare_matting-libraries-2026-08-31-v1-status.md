# 比较文档：抠图方案 vs island_cut 现状

> **Date:** 2026-08-31
> **Topic:** island-cut
> **类型:** compare（外部方案实现 vs 本项目实现程度，现状快照）
> **版本:** v1（首版）

> 说明：`.claude/repo` 下现有 8 个参考仓库均为 B站/五子棋/俄罗斯方块类，无抠图类项目，故外部数据取自各库公开特性与模型资料；**标注「估」的数字为公开资料推算，未实测**。本文只记录现状与差距，不含选型建议（建议见 intent/interior-white-region-2026-08-31-v1-design.md）。

## 对比对象

外部 7 项 + 本项目：

1. rembg + u2netp（4.7MB 轻量模型）
2. rembg + 全尺寸模型（u2net ~168MB / silueta ~43MB / isnet ~170MB）
3. transparent-background（InSPyreNet，基于 torch）
4. backgroundremover（rembg 的 CLI 封装，另叠 torch）
5. pymatting（纯数值 alpha matting）
6. opencv-python-headless（cv2）
7. scikit-image
8. 本项目：island_cut（scipy.ndimage + numpy + PIL，见 backend/pyproject.toml:16-18）

## 主对比表

| 方案 | ①依赖与 Docker 磁盘增量 | ②运行内存峰值 | ③2vCPU 单张耗时 | ④识别能力边界 | ⑤内部白区/洞支持 | ⑥300MB 预算 | 本项目现状对照 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rembg + u2netp | +250~400MB 估（onnxruntime + opencv-headless + pymatting/numba 依赖链）+ 模型 4.7MB | 估 ~100-250MB | 估 0.3~1.5s | 显著性主体抠图；输入重采样至 320×320；简单主体可用，发丝级边缘一般 | ❌ 不提供：显著性模型倾向把主体内部洞作为前景填掉 | ⚠️ 勉强可行，峰值需实测 | 本项目无 AI 抠图；白底/透明底两模式已覆盖现有输入场景 |
| rembg + 全尺寸模型 | 磁盘增量同上 + 模型 43~176MB | 估 ~350-700MB | 估 1~8s | 质量好 | ❌ 同上 | ❌ 模型权重即占预算大半 | 不具备 |
| transparent-background | torch CPU 磁盘 +~700MB 量级 估 + 模型百 MB 级 | 估 ~500MB-1GB | 秒级 | 边缘 matting 质量好 | ❌ 同上 | ❌ 超预算 | 不具备 |
| backgroundremover | 在 rembg 之上叠 torch | 更高 | — | rembg 的 CLI 壳 | ❌ 同上 | ❌ 超预算 | 不具备 |
| pymatting | +numba/llvmlite ~100-150MB | 图像尺寸相关，大图 KNN 可达数百 MB 估 | 秒级（大图更慢） | **不识别主体**，仅在已有 mask 上精修半透明 AA 边缘 | 不适用 | ⚠️ 小图可行 | 本项目 white 模式输出二值 alpha（255/0），无半透明精修环节 |
| opencv-python-headless | +~120-160MB 估 | 图像缓冲级 | ms 级（GrabCut 秒级） | floodFill / GrabCut / 连通域 / 轮廓 | ✅ findContours RETR_CCOMP 层级天然分外轮廓与内洞 | ⚠️ 可行 | 本项目用 scipy.ndimage 实现了等价原语（label/泛洪/闭运算），无 cv2 依赖 |
| scikit-image | +~60-100MB 估（networkx/imageio 等） | 图像缓冲级 | ms 级 | measure.label / regionprops / clear_border 便利封装 | ✅ 支持 | ⚠️ 可行 | 本项目已手写等价逻辑（小连通域归属主岛，service.py:97-114），未用 skimage |
| **本项目 island_cut** | +0（依赖已在） | 1~4MP 约几十 MB；40MP 极端输入峰值可超 300MB（见差距 3）估 | 0.1~0.5s（4MP 量级，log elapsed_ms 口径） | 白底/透明底两模式；复杂背景无法处理 | 语义已就位但未暴露：内部白区 = 白色连通域中不与边界连通者，当前一律并入岛屿 | ✅ 典型尺寸可行 | — |

## 本项目现状（基于代码扫描）

- **依赖**：fastapi / numpy / pillow / scipy 等（backend/pyproject.toml:7-20）；无 cv2、skimage、torch、onnxruntime。
- **算法**：`detect_mode` 自动判定 alpha/white（service.py:54-56）；white 模式 `flood_fill_background` 边界泛洪定背景（service.py:59-64）→ `binary_closing` 闭运算 → label 主岛 + 小连通域归属（service.py:78-115）→ 阅读序排序（service.py:118-136）→ 逐岛 bbox+pad 裁剪写 alpha（service.py:139-158）。
- **API**：POST /api/island-cut/jobs（同步 def，线程池执行）+ GET pieces/full/zip + DELETE（router.py:40-112）；上传 ≤50MB（router.py:24）、像素 ≤4000 万（router.py:25）。
- **存储**：内存注册表 + 临时目录 + TTL 3600s 惰性清理（store.py:27-75）；job 目录只落 pieces PNG 与整图 PNG，**不落原图**（store.py:36-52）。
- **输出语义**：内部白区当前作为白色不透明像素并入所属岛（white 模式 mask 内 alpha=255，service.py:156-158）；alpha 模式保留 mask 内原 alpha（service.py:152-155），内部洞本就透明。

## 差距与问题（现状现象）

1. **内部白区无法区分与选择**：一律并入岛屿保留白色，无编号、无元数据、无选择接口——这是本次新需求指向的直接缺口。
2. **复杂背景输入超出两模式能力**：alpha/white 之外的照片背景（渐变、杂色、实景）当前无法处理；此类需求在外部对应 rembg 等模型方案。
3. **像素上限与内存预算不匹配的隐患**：MAX_PIXELS=40MP（router.py:25）允许的极端输入下，`ndimage.label` 的 int32 输出（40MP ≈ 160MB）+ bool mask + 裁剪副本 + 内存中 zip 打包（router.py:94-105）可推高峰值超过 300MB 容器预算；1~4MP 典型输入约几十 MB 量级（估）。
4. **rembg 引入代价的事实**：其依赖链额外带入 opencv-headless 与 pymatting/numba；模型默认首跑经 GitHub release 下载（pooch），国内服务器可达性存疑，需 COPY 进镜像；显著性模型填洞特性与「内部白区识别」需求正交——上了 rembg 该功能仍需自行连通域后处理。
5. **store 不落原图**：任何「基于原结果再加工」的接口（如勾选白区后重切）目前缺少输入数据来源。

## 数据来源备注

- 磁盘/内存/耗时数字（估）为公开资料推算，正式采纳前需在目标容器实测。
- 模型体积：u2netp ~4.7MB / u2net ~168MB / silueta ~43MB / isnet ~170MB，来自各模型发布页公开信息。
- rembg 依赖链、模型下载机制来自其官方仓库文档/代码。
