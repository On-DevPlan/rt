"""MP4 → 透明 Animated PNG（APNG；max-island 算法；自完备）。

与 video_island / video_webp 同算法，仅编码器换为 PIL Animated PNG（save_all）。
APNG 在所有现代浏览器原生支持、保留 8 位 alpha，体积比 GIF 略大。
"""