> **原始意图（用户原话）**
> > 可以把视频的主体色块 结合岛屿算法 把一个视频转化车带透明通道的 sheet, 可以实现吗?
>
> 复述：能否结合 island_cut 的岛屿算法，把一段视频处理成带透明通道的 sprite sheet？

---

# Intent: video-to-sheet「视频 → 透明 sprite sheet」预测设计（v1）

> **Date:** 2026-08-31
> **Topic:** island-cut
> **类型:** intent doc（预测设计）
> **版本:** v1（首版；复用 island_cut 岛屿算法件的视频处理流水线，与 interior-white-region v2、ai-matting-ladder v1 并列的第三个设计想法）
> **状态:** 试验
> **核心问题:** 把短视频（典型：像素画角色待机/跑动循环）转化为带透明通道的 sprite sheet + 元数据，复用 island_cut 既有算法件约七成。

相关文档：[interior-white-region-2026-08-31-v2-design.md](./interior-white-region-2026-08-31-v2-design.md) · [ai-matting-ladder-2026-08-31-v1-design.md](./ai-matting-ladder-2026-08-31-v1-design.md) · [../basic/app-animation-asset-formats-2026-08-31-v5-concepts.md](../../basic/app-animation-asset-formats-2026-08-31-v5-concepts.md)（sprite sheet 知识底座）

## 本版要验证的假设

1. island_cut 的算法件（色距掩膜 → 泛洪背景 → closing → 连通域过滤）在逐帧视频场景下无需重写即可复用——「白色」泛化为「背景色距」，下游结构不变。
2. 逐帧闪烁可由「全片估计一次（背景色 + 阈值时序中位数）、逐帧只判定不调参」压制到肉眼不可见。
3. 像素画输入（无抗锯齿、平色块、原生 ≤128×128）下，mask 无需羽化即边缘干净；300MB 内存预算内流式处理无压力。
4. ffmpeg 以子进程方式调用（解帧 + tile 拼图）即可满足 IO，不引入 PyAV 等新 Python 依赖。

## 一、设计原则

| # | 原则 | 体现 |
| - | --- | --- |
| 1 | 复用岛屿件 | 泛洪/closing/连通域过滤/裁剪全部复用，只把 is_white 泛化为 is_bg |
| 2 | 流式处理 | 解码→处理→落盘逐帧流式，任何时刻内存中只有常数个帧缓冲 |
| 3 | 全片一次调参 | 背景色与阈值全片估计一次，逐帧只判定——防逐帧闪烁（本设计最大质量风险） |
| 4 | 统一画布 | 先扫全帧取 union bbox 定统一画布，所有帧锚定同一坐标系——防 sprite 抖动 |
| 5 | 子进程 IO | ffmpeg 子进程解帧/拼图，主服务不引视频解码依赖 |
| 6 | 像素画优先 | 目标输入为像素画/赛璐璐素材；实拍视频定位为「尽力而为」 |

## 二、模块拆分

```
backend/src/rt_backend/island_cut/
├── video_sheet.py     # 新：流水线编排（解帧→估计→逐帧掩膜→去重→拼装）
│                      #   依赖 service.py 的泛洪/closing/连通域原语
├── service.py         # 抽出可复用原语（flood_fill_background 已独立，closing/min_area 传入式）
├── router.py          # + POST /api/island-cut/video-sheet（multipart 视频）
└── schemas.py         # + VideoSheetRequest/VideoSheetResponse
backend/tests/
└── test_video_sheet.py # 新：合成测试视频的回归用例
```

不新增 Python 依赖：视频解码与拼图走 ffmpeg 子进程（docker 镜像需加装 ffmpeg 二进制）。

## 三、数据流（关键场景）

**场景 1：上传 → 全片估计**

POST 视频（≤50MB、时长 ≤30s、边长 ≤1080）→ ffmpeg 抽帧（低帧率素材配合 mpdecimate 丢重复帧）→ **估计阶段**：逐帧边缘带采样 → 背景色 = 各帧边缘色众数的时序中位数；阈值 = 全片固定（单参数，缺省沿用色距容差思路）。

**场景 2：逐帧处理（流式）**

每帧：BGR→RGBA → `is_bg = 色距(pixel, bg_color) < tol` → `fg = ~flood_fill_background(is_bg)` → `binary_closing` → 连通域过滤（max-area 主体 + min_area 去渣）→ alpha 二值化（像素画）或软阈值羽化（实拍）→ 原生分辨率档位检测 → 最近邻缩回 → 统一画布裁剪 → 落 PNG 帧。

**场景 3：去重与拼装**

帧指纹（缩略 hash）去重 → 记录每帧时长（1/源fps 或重复帧计数加权）→ ffmpeg tile 或 PIL 拼网格 sheet → 元数据 JSON（帧矩形、时长、循环名）→ 返回 zip（sheet.png + frames.json + 预览 GIF）。

**场景 4（可选二期）：idle/run 分循环**

按帧间隔聚类切分循环段，各自导出 sheet——一期先单循环整段导出。

## 四、关键决策（含选型说明）

1. **抠底 = 色距掩膜 + 泛洪，非 chroma key 滤镜直出**。理由：island_cut 的泛洪语义（贴边连通才算背景，service.py:59-64）天然防「主体内部与背景同色被误抠」；ffmpeg chromakey 是无泛洪语义的全局色键，主体含背景色时翻车。备选 rembg：AI 显著性会填掉内部透明区，且超内存预算（见 ai-matting-ladder 文档）。
2. **背景估计全片一次**。理由：逐帧独立调参是闪烁之源；时序中位数抗单帧异常。备选逐帧自适应：质量上限高但引入时序抖动，一期不取。
3. **统一画布而非逐帧 bbox**。理由：逐帧裁剪会让 sprite 在 sheet 里跳动；union bbox 一次定锚是游戏 sprite 惯例。备选逐帧 bbox + 帧间对齐：二期优化。
4. **帧去重保留时长信息**。理由：像素动画原生 8~12fps，视频常 24/30fps——重复帧直接决定循环时长；丢失则播放速度错乱。
5. **解码走 ffmpeg 子进程**。理由：零 Python 依赖增长（300MB 预算纪律）；PyAV 带来 libav 二进制级耦合，除非后续需要逐帧 seek 精控，一期不取。代价：docker 镜像 +ffmpeg 二进制（~80MB 磁盘，无运行时常驻）。
6. **像素画二值 alpha、实拍软阈值**。理由：像素画无抗锯齿，二值干净且体积小；实拍边缘有渐变，硬切出白边——按输入类型选模式，参数可配。
7. **时长/边长上限收紧**（时长 ≤30s、边 ≤1080、50MB 沿用）。理由：流式下内存安全，但 CPU 时间与磁盘峰值仍随时长线性涨；单人使用按素材现实定（像素循环普遍 ≤10s）。
8. **一期不做**：idle/run 自动分循环、帧间运动补偿对齐、实拍级 matting 精修、多循环元数据 schema——防蔓延，均为二期。

## 五、接口 / 代码骨架

```python
# schemas.py 新增
class VideoSheetResponse(BaseModel):
    job_id: str
    frame_count: int
    fps_hint: float            # 去重后建议播放帧率
    sheet_url: str             # /api/island-cut/jobs/{id}/sheet.png
    frames_json_url: str
    preview_url: str           # 预览 GIF
    canvas: dict               # {x, y, w, h} 统一画布在原帧坐标系

# video_sheet.py 骨架
def build_sheet(video_bytes: bytes, out_dir: Path, params: VideoSheetParams) -> VideoSheetResult:
    frames_dir = extract_frames(video_bytes, out_dir)          # ffmpeg 子进程，mpdecimate
    bg_color, tol = estimate_background(frames_dir)            # 边缘采样 + 时序中位数，全片一次
    canvas = scan_union_bbox(frames_dir, bg_color, tol)        # 先扫全帧定统一画布
    for f in frames_dir: render_alpha_frame(f, bg_color, tol)  # 流式：复用 service 泛洪/closing/连通域
    kept = dedupe(frames_dir)                                  # 缩略 hash 指纹 + 重复帧计数
    return pack_sheet(kept, canvas, out_dir)                   # tile/PIL 网格 + frames.json + 预览 GIF

# router.py 新增
POST /api/island-cut/video-sheet   # multipart 视频 → VideoSheetResponse（同步 def，线程池）
```

## 六、职责边界

- **video_sheet.py**：视频流水线编排（估计/去重/拼装），复用 service 原语，不懂 HTTP。
- **service.py**：保持纯图像原语提供方；不为视频特化参数（色距掩膜在 video_sheet 内实现，泛洪复用）。
- **router.py**：校验（时长/边长/大小）、编排、错误码。
- **store.py**：复用 job 体系；video job 落帧目录 + sheet 产物，TTL 一致。
- 防蔓延：不碰前端交互、不做循环编辑器、不做实时预览流、不做云 API——均二期/独立议题。

## 七、改动范围（影响面）

| 模块 | 现状 | 改后 | 影响 |
| --- | --- | --- | --- |
| video_sheet.py | 不存在 | 新增（流水线编排） | 新文件，复用 service 原语 |
| service.py:59-64,173-174 | 泛洪/闭运算已独立可复用 | 原样复用，不改动（若复用需要参数化，最小重构） | 零或极小 |
| router.py | 5 端点 | +video-sheet 1 端点 | 纯新增 |
| schemas.py | Cut 系列 | +VideoSheet 系列 | 纯新增 |
| store.py | 图像 job | +video job 帧目录 | 结构小增 |
| docker 镜像 | 无 ffmpeg | +ffmpeg 二进制 | 磁盘 +~80MB，无运行时常驻 |
| tests | 图像回归 | +合成视频用例（ffmpeg 生成测试素材） | 纯新增 |

## 八、迁移 / 实施路径

- **V1 整段流水线**：单循环整段导出（估计→逐帧→去重→sheet+JSON+预览 GIF）。验收后即可用于像素素材。
- **V2（可选）**：idle/run 分循环 + 元数据 schema 升级。
- **V3（可选）**：实拍级边缘羽化调优 + 帧间对齐补偿。

## 九、验收标准

| # | 验证项 | 方法 |
| --- | --- | --- |
| 1 | 合成像素画测试视频（ffmpeg 生成纯色底 + 平移方块）全流程出 sheet，帧数/时长正确 | 新增单测 |
| 2 | 主体内部含背景同色区块不被误抠 | 泛洪语义单测（帧级） |
| 3 | 相邻帧参数不漂移：同一素材连续两次处理结果逐字节一致 | 确定性单测 |
| 4 | 重复帧去重后 fps_hint 正确、循环时长与源一致 | 合成变速素材单测 |
| 5 | 1080p×30s 输入流式处理峰值 RSS < 300MB | /usr/bin/time -v 实测 |
| 6 | sheet.png + frames.json 可被标准播放器消费（Canvas steps 演示页） | 手验 |
| 7 | 非视频文件/超时长输入 4xx 且主服务不崩 | 边界单测 |

## 十、待用户拍板的决策

| # | 决策 | 推荐 |
| --- | --- | --- |
| 1 | 输入范围一期定多大 | 像素画/赛璐璐优先（二值 alpha）；实拍「尽力而为」或暂不承诺 |
| 2 | 时长上限 | 30s（像素循环普遍 ≤10s，留余量） |
| 3 | sheet 排布 | 网格（列数按最长循环自适应）vs TexturePacker 式装箱——一期网格 |
| 4 | 元数据格式 | Aseprite JSON 兼容（hash 格式）——现成播放器生态可直连 |
| 5 | 是否保留逐帧 PNG 目录给前端二次加工 | 保留（磁盘换灵活性，TTL 一致清理） |
| 6 | ffmpeg 进 docker 镜像 vs 主服务 pip 装 imageio-ffmpeg | 镜像装 ffmpeg 二进制（apt），依赖纪律干净 |

## 十一、参考

- 代码：backend/src/rt_backend/island_cut/service.py:59-64（泛洪）、:167-171（fg 判定）、:173-174（closing）、router.py:24-25（上限）、store.py:36-52（job 结构）
- 本主题文档：basic/app-animation-asset-formats-2026-08-31-v5-concepts.md（sprite sheet/像素画回收知识底座）· intent/interior-white-region-2026-08-31-v2-design.md · intent/ai-matting-ladder-2026-08-31-v1-design.md
- 外部参照：ffmpeg mpdecimate/tile 滤镜文档、Aseprite JSON 导出格式、TexturePacker 装箱算法
