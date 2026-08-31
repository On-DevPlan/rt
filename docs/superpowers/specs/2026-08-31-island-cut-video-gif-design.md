# Island Cut 多方案扩展：MP4 → GIF 子方案 + 模块内 Tab 导航

> 日期：2026-08-31
> 状态：已通过 brainstorming，待用户复核后进入 writing-plans

## 1. 背景与目标

`rt` 项目的 `island-cut` 模块当前只支持**静态图片**按连通域岛屿切割，输出多张带透明通道的 PNG 并打包 ZIP。需求扩展两点：

1. **新增 MP4 → 透明 GIF 子方案**：参考 `largest_island_gif.py` 的"每帧边框中位背景估计 + 最大岛屿 + 统一裁剪 + NEAREST 缩放 + disposal=2 GIF 编码"算法，移植为后端流式服务；前端页面同样支持上传并预览/下载。
2. **模块内 Tab 导航**：用户主动指出"在头部做一个导航条，实现不同的媒体处理方案。后续还可能有 MP4 → APNG 等等方案"。本次设计一次到位：模块升级为"多方案容器"，新增新方案不再碰架构。

约束：
- 单页面 + tabs（用户拍板）：仅一个路由 `/island-cut/studio`；tab 状态机切换 image-cut / video-gif / video-apng 占位。
- 视频解码 = PyAV（用户拍板）：流式、不需系统 ffmpeg、依赖最小。
- 参数 = 前端表单可调（用户拍板）：与现有 image-cut 一致，后端 Pydantic schema + 前端滑杆，无后端配置默认隐藏。
- 不做：AI 抠视频（与 ai-matting-ladder L1 独立）、MP4 → APNG 真实实现（占位卡即可）、批量处理、海报帧导出、客户端视频预览。

## 2. 关键事实（已核实）

- 参考脚本 `largest_island_gif.py` 的算法五要素：①边框中位 bg（对角落水印鲁棒）；② `diff > tol` 前置掩码 + 闭运算 + 连通域 + **只取最大分量** + `binary_fill_holes`；③**全帧 union 包围盒** + pad；④ **NEAREST 缩放**（LANCZOS 在二值 alpha 上振铃会把远端小岛桥接回主体，且会修改岛屿内部像素色）；⑤PIL `save GIF, save_all, disposal=2, loop=0, optimize` 防残影。这五点逐行移植。
- moviepy 重且在 Py 3.12 上版本分支多；用 PyAV `av.open(...)` + `for frame in container.decode(video=0)` 直接流式访问 numpy RGB 数组，避免全帧加载 OOM（30s@1080p×30fps = ~5.3GB 原始 RGB）。
- PyAV 的 `av` 包以 wheel 形式携带 libav（`av>=12` 支持 cp312），无需在 docker 镜像装 ffmpeg；docker 镜像体积影响约 +5~10MB。
- `binary_fill_holes` 把主体内部浅色高光补回（参考脚本第 67 行）——避免"主体中间透明"。
- "跳过开头/结尾淡入淡出帧"靠背景差异阈值 5 过滤（参考脚本 135 行）；短视频也常需要。

## 3. 方案选型

**采用：模块内 `video_island/` 子 feature + 单页面 tabs 切换 + 独立 `IslandVideoJobStore`。**

| 候选 | 取舍 | 结论 |
|---|---|---|
| 新增 video_island 子目录 vs 在 service.py 加 if 分支 | 子目录保持职责单一、image 现有 11 个测试与新代码互不干扰、未来加 video-apng 可直接复制度量 | ✓ 子目录 |
| 复用 IslandJobStore vs 新 IslandVideoJobStore | metadata 形状不同（video 有 src_fps/out_fps/frame_count/duration_sec vs image 有 mode/width/height/piece_count）；统一 store 复杂度和耦合度都高 | ✓ 独立 store |
| `imageio[ffmpeg]` vs moviepy vs PyAV | 三者均能跑；imageio 全加载风险；moviepy 依赖链重；PyAV 流式 + wheel 自带 libav | ✓ PyAV |
| 单页 tabs vs 独立路由 + 导航条 | 用户拍板单页 | ✓ 单页 |
| tabs 组件内联在 IslandCutPage vs 抽到 components/IslandCutNavBar | NavBar 未来可能加更多 UI（深链、状态指示）；抽出便于测试与复用 | ✓ 抽出 |
| tab 切换保留组件状态 vs 重置 | 调参反复切回丢参数体验差；用 CSS 隐藏 + 组件常驻 | ✓ 保留 |

## 4. 决策记录

| 决策 | 结论 |
|---|---|
| 视频解码 | PyAV（`av>=12`） |
| Tab 持久化 | 各 tab 面板组件常驻，切 tab 仅 CSS 隐藏 |
| 参数暴露 | 后端 Pydantic 默认值 + 前端表单可调（与 image-cut 一致） |
| 临时持久化 | 独立 `IslandVideoJobStore`，与 image 同机制（内存注册表 + 临时目录 + TTL） |
| 跳帧策略 | `step = round(src_fps / out_fps)`，与参考脚本一致 |
| 背景异常帧过滤 | 边框 bg 与"全局 bg 中位"差 >5 的帧跳过 |
| 输出尺寸 | max-size=0 不缩放；否则 union bbox + pad → 长边 = max-size，NEAREST |
| GIF 编码 | PIL `save(format='GIF', save_all=True, append_images=…, disposal=2, loop=0, optimize=True)`；delay = round(1000 / out_fps) ms |
| 预览图 | 沿用参考脚本 3 帧棋盘格（首/中/尾）`preview.png`，随 job 落盘并由 preview_url 暴露 |
| 帧/时长上限 | max_frames=600、max_duration_sec=60（可调默认；超限返回 413） |
| 上传大小 | 沿用现有 50MB（nginx `client_max_body_size`）；短视频（<60s@720p）通常 10~30MB OK |
| 视频→APNG | 占位 Panel（"APNG 即将到来"+说明链接到 ai-matting-ladder docs）；不落实现 |
| nginx / docker 镜像 | 不改（PyAV wheel 自带 libav，无系统 ffmpeg 依赖） |
| 落盘路径 | 临时目录 `${tempfile.gettempdir()}/rt_island_cut_video/<job_id>/`，TTL 60min 惰性清理 |

## 5. 架构与数据流

```
前端（单页 /island-cut/studio）
  │
  │ IslandCutNavBar(activeTab)
  │
  ├── ImageCutPanel ── POST /api/island-cut/jobs           ─→ (image 现有链路)
  │                     └── /zip /pieces/{f} /full.png /capabilities
  │
  └── VideoGifPanel ── POST /api/island-cut/video/jobs
                       ├── multipart video + params JSON
                       └── server.process_video(data, params)
                              ├── PyAV decode（流式）
                              ├── per-frame: border-median bg → max-island mask
                              │                → binary_fill_holes
                              ├── 全帧 union bbox + pad + 缩放
                              ├── 3 帧棋盘 preview
                              └── PIL GIF save(disposal=2, loop=0)
                       返回 {job_id, gif_url, preview_url, frame_count, src_fps,
                              out_fps, width, height, duration_sec, elapsed_ms}
                       客户端 <img src=gif_url> + <a download> 即可
```

## 7. 后端模块设计

### 7.1 新子包 `backend/src/rt_backend/island_cut/video_island/`

| 文件 | 职责 |
|---|---|
| `__init__.py` | 空标记 |
| `schemas.py` | `VideoCutParams`(fps, max_size, bg_tol, pad, max_duration_sec, max_frames)；`VideoCutResponse`(job_id, frame_count, src_fps, out_fps, width, height, duration_sec, elapsed_ms, gif_url, preview_url) |
| `service.py` | `process_video(data: bytes, params: VideoCutParams) -> VideoResult`（纯函数无 I/O）；constants `MODEL_BG_TOL=50`、`MODEL_PAD=6` 仅为默认值 |
| `store.py` | `IslandVideoJobStore`（参照 `IslandJobStore` 模式：内存注册表 + 临时目录 + TTL 惰性清扫；`VideoJob{id, dir, gif_path, preview_path, meta, created}`） |
| `router.py` | `build_video_router(store_provider)`：POST/GET/DELETE 端点 |

### 7.2 `service.py` 算法骨架（关键函数）

```python
def process_video(data: bytes, params: VideoCutParams) -> VideoResult:
    container = av.open(io.BytesIO(data))
    stream = container.streams.video[0]
    src_fps = float(stream.average_rate or 30.0)
    duration = float(container.duration / av.time_base) if container.duration else None
    step = max(1, round(src_fps / params.fps))
    out_fps = src_fps / step
    # ... 受 max_frames / max_duration 约束
    
    frames_rgb, masks, bgs = [], {}, []
    for idx, frame in enumerate(container.decode(stream)):
        if idx % step: continue
        rgb = frame.to_ndarray(format="rgb24")  # h,w,3
        bgs.append(_frame_bg(rgb, border=10))
        frames_rgb.append(rgb)
    container.close()
    
    kept_idx = [i for i, b in enumerate(bgs)
                if np.abs(b - np.median(bgs, axis=0)).max() <= 5]
    
    global_bg = np.median(np.array(bgs), axis=0)
    masks = {i: _build_mask(frames_rgb[i], global_bg, params.bg_tol)
             for i in kept_idx}
    
    # union bbox + pad
    H, W = frames_rgb[0].shape[:2]
    union = np.zeros((H, W), bool)
    for m in masks.values(): union |= m
    rows, cols = np.where(np.any(union, axis=1))[0], np.where(np.any(union, axis=0))[0]
    y0, y1 = max(0, rows[0]-params.pad), min(H, rows[-1]+1+params.pad)
    x0, x1 = max(0, cols[0]-params.pad), min(W, cols[-1]+1+params.pad)
    
    tw, th = x1 - x0, y1 - y0
    if params.max_size and max(tw, th) > params.max_size:
        s = params.max_size / max(tw, th)
        tw, th = max(1, round(tw*s)), max(1, round(th*s))
    
    out_frames = []
    for i in kept_idx:
        rgba = np.dstack([frames_rgb[i], masks[i]*255]).astype(np.uint8)
        im = Image.fromarray(rgba, "RGBA").crop((x0, y0, x1, y1))
        if (tw, th) != im.size: im = im.resize((tw, th), Image.NEAREST)
        out_frames.append(im)
    
    # save gif + 3-frame preview (checkerboard)
    gif_buf = io.BytesIO()
    out_frames[0].save(gif_buf, format="GIF", save_all=True,
                       append_images=out_frames[1:],
                       duration=max(2, round(100 / out_fps)) * 10,
                       loop=0, disposal=2, optimize=True)
    preview_buf = io.BytesIO()
    _save_preview(out_frames, preview_buf)
    return VideoResult(gif_bytes=gif_buf.getvalue(),
                       preview_bytes=preview_buf.getvalue(),
                       frame_count=len(out_frames), src_fps=src_fps,
                       out_fps=out_fps, width=tw, height=th, ...)
```

### 7.3 `core/config.py` 新增字段

```
video_island_dir: str = ""                          # 空 → tempdir/rt_island_cut_video
video_island_ttl_min: int = 60                      # 与 image 同机制
```

### 7.4 `main.py` lifespan 增加

```
video_store = IslandVideoJobStore(
    root=Path(settings.video_island_dir) or Path(tempfile.gettempdir())/"rt_island_cut_video",
    ttl_sec=settings.video_island_ttl_min * 60)
app.state.video_store = video_store
app.include_router(_build_video_island(lambda r: r.app.state.video_store))
```

### 7.5 端点契约

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/island-cut/video/jobs` | multipart `=file=` + `params` JSON 表单字段 |
| `GET`  | `/api/island-cut/video/jobs/{id}/gif` | 透明 GIF） |
| `GET`  | `/api/island-cut/video/jobs/{id}/preview.png` | 3 帧棋盘 preview |
| `DELETE` | `/api/island-cut/video/jobs/{id}` | 手动清理 |

### 7.6 `backend/pyproject.toml` + `uv add av>=12`

## 8. 前端模块设计

### 8.1 新结构

```
src/modules/island-cut/
├── module.meta.js          # 不动（仅一个页面 /island-cut/studio）
├── pages/IslandCutPage.jsx # 改写：包 NavBar + tabs 状态机
├── schemes.js              # 新：ISLAND_CUT_TABS 配置表
├── pages/ImageCutPanel.jsx # 从原 IslandCutPage body 抽出（API 改用 imageCutApi）
├── pages/VideoGifPanel.jsx # 新：dropzone + 6 滑杆 + 结果 GIF 预览 + 下载
├── pages/VideoApngPanel.jsx # 新：占位卡
├── components/IslandCutNavBar.jsx # 新：tabs/chips，深色 active 高亮
├── services/imageCutApi.js     # 从 islandCutApi.js 改名
├── services/videoCutApi.js     # 新
├── services/islandCutApi.js    # 保留 DEFAULT_PARAMS 重新导出 (向后兼容)
└── pages/IslandCutPage.module.css # 增 tab 切换、apng 占位卡片样式
```

### 8.2 `schemes.js` 结构

```js
import ImageCutPanel from './pages/ImageCutPanel.jsx'
import VideoGifPanel from './pages/VideoGifPanel.jsx'
import VideoApngPanel from './pages/VideoApngPanel.jsx'

export const ISLAND_CUT_TABS = [
  { id: 'image-cut',   label: '图片切割',    Component: ImageCutPanel },
  { id: 'video-gif',   label: '视频 → GIF', Component: VideoGifPanel },
  { id: 'video-apng',  label: '视频 → APNG', badge: '未来', Component: VideoApngPanel },
]
```

### 8.3 `IslandCutPage.jsx` 骨架

```jsx
const [active, setActive] = useState(ISLAND_CUT_TABS[0].id)
return
  <div className="page-stack">
    <IslandCutNavBar tabs={ISLAND_CUT_TABS} activeId={active} onChange={setActive}/>
    {ISLAND_CUT_TABS.map(t =>
      <div key={t.id} hidden={t.id !== active}>
        <t.Component />  {/* 各 tab 面板独立状态，切 tab 不丢 */}
      </div>
    )}
  </div>
```

### 8.4 `VideoGifPanel.jsx` UI

- dropzone（拖 MP4 / 点击选）
- 6 滑杆：fps(1-30)、max_size(64-1024, 0=不缩放)、bg_tol(1-255)、pad(0-50)、max_duration_sec(10-300)、max_frames(60-1500)
- 提交（disabled 无文件 / loading）
- 结果：GIF `<img>` + 棋盘 preview 缩略 + `⬇ 下载 GIF` + 帧数/duration/elapsed 信息

### 8.5 `IslandCutNavBar.jsx`

- tab chip 列表：active 态加深色边框 + 加粗字重；未来 badge 用 `.badge` 标签
- hover 有边框颜色过渡（复用全局 `.chip` 样式可选择）

## 9. 测试策略

### 9.1 后端 `tests/test_video_island.py`

- `test_decode_synthetic_mp4`：fixture 生成 5 帧 RGB（numpy → imageio mimsave → bytes 模拟 MP4；或装 `av` 后用 `av.open` 写帧序列直接），传入 `process_video` → 断言 GIF 字节、PIL 打开正常、frame_count=5、disposal=2、out_fps=src_fps/step、union bbox 期望值
- `test_bg_tol_filters_watermark`：合成含水印的背景图，bg_tol=50 → mask 不含水印连通域（与参考脚本一致）
- `test_max_size_resize`：max_size=64 → 输出尺寸长边 ≤ 64
- `test_border_bg_diff_filters_intro_outro`：开头 2 帧背景异常 → kept_idx 跳过
- `test_router_post_gif_preview`：`TestClient` POST multipart → 200 / video job，GET gif → 200 image/gif，GET preview → 200 image/png
- `test_store_ttl`：TTL 0.05s → sleep 0.06 → 404
- `test_oversize_video`：超 max_frames/max_duration → 413
- `test_image_regression`：现有 `test_island_cut.py` 11 个全绿（video 不污染 image）

### 9.2 前端

- `pnpm run build`（模块聚合错误检测：`*Page.jsx` / `*Panel.jsx` 后缀不匹配 Page 收敛、但 `*Panel.jsx` 不在 `*Page.jsx` glob 中，不会被当作入口误注册——验证 schema glob 不变）
- 手动 server 验证（后续）

## 10. 迁移 / 实施路径

1. **后端骨架**：建 `video_island/` 四文件；pyproject + `uv add av`；config + main.py 挂载
2. **算法移植**：参考脚本逐行搬进 `service.py`，并加单元测试
3. **端点 & store**：`router.py` + `store.py` + TTL 测试
4. **前端拆分**：抽出 ImageCutPanel + 写 schemes.js + IslandCutNavBar + VideoGifPanel + VideoApngPanel + apis 拆 split
5. **样式 + polish**：NavBar 样式、视频 GIF 预览棋盘格背景、apng 占位
6. **回归**：现有 island_cut 测试 + frontend build + 现有部署链路不动

## 11. 验收标准

| # | 验证项 | 方法 |
| --- | --- | --- |
| 1 | 后端测试全绿，含新 video_island 用例 | `uv run pytest -q` |
| 2 | 前端 build 通过 | `pnpm run build` |
| 3 | video→gif 端到端：上传 MP4 → 返回 GIF（disposal=2、loop 0、optimize） | `pytest` + curl 验 |
| 4 | 预览图存在且尺寸合理 | `pytest` |
| 5 | 各 tab 独立状态，切回不丢参数 | 浏览器手验（后续） |
| 6 | image-cut 完全无回归 | 现有 11 测试全绿 |
| 7 | 占位 tab "视频 → APNG" 不报错、清晰标识"未来" | 浏览器手验 |
| 8 | 后端 RSS 仍在 ≤300MB 预算内（30s@720p 单 job） | 服务器实测（后续） |
| 9 | nginx / docker 镜像无变更 | git diff |

## 12. 待拍板（与已拍板汇总）

| # | 决策 | 结论 |
| --- | --- | --- |
| 1 | tab 架构 | ✓ 单页 + tabs（用户拍板） |
| 2 | 视频解码 | ✓ PyAV（用户拍板） |
| 3 | 参数范围 | ✓ 前端表单可调（用户拍板） |
| 4 | store 独立 | video 独立 IslandVideoJobStore |
| 5 | 帧/时长上限默认 | max_frames=600 / max_duration_sec=60（待服务器实测调整） |
| 6 | APNG tab | 占位卡，不落实现 |

## 13. 参考

- 参考脚本：`D:\code\a_py\proj\bigpy\1000-support-cmd\file_process\img\gif\largest_island_gif.py`
- 现实现：`backend/src/rt_backend/island_cut/{service.py,router.py,store.py,schemas.py}`
- manifest：`src/modules/island-cut/module.meta.js`
- 关联设计：`.claude\repo\_self\island-cut\intent\ai-matting-ladder-2026-08-31-v2-design.md`（独立路线，本设计不与其耦合）