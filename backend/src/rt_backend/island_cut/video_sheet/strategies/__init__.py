"""MP4 → 透明 sprite sheet 策略包。

不同处理阶段作为独立子模块，便于单独替换或测试：
  - bg       背景色估计
  - fg       前景掩膜（色距 + 边界泛洪 + 最大连通域）
  - feather  边缘羽化
  - io       ffmpeg 抽帧 + 临时文件落盘

service.process_video 是把这些策略编排起来的薄壳；不参与具体算法。
"""
from . import bg, fg, feather, io  # noqa: F401