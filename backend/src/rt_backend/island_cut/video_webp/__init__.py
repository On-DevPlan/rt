"""MP4 → 透明 Animated WebP（max-island 算法；自完备、不复用 video_island）。

算法与 video_island 完全一致（边框中位 bg + max-island + NEAREST），
仅编码器换为 PIL Animated WebP（lossless 保 alpha）。
"""