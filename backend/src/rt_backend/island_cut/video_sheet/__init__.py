"""MP4 → 透明 sprite sheet + 元数据（独立 service；移植 .tool/video-sheet/scripts/build_sheet.py）。

算法（与 build_sheet.py 一致；本文件不 import 横向隔离）：
  1. ffmpeg 抽帧（带 mpdecimate 去重复帧）
  2. 每帧独立 bg 估计 + 色距掩膜 + 边界泛洪 + 仅最大岛 + 高斯羽化
  3. 全帧 union bbox（统一画布）
  4. 拼 sprite sheet + frames.json + 预览 APNG/WebP

与 video_island / video_webp / video_apng 不同的算法（不是 max-island 系列）。
"""