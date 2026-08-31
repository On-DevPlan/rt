"""ffmpeg 抽帧 + 临时文件 IO 策略。

extract_frames 走 ffmpeg 子进程（含 mpdecimate 去重 + 重采样到目标 fps）。
_save_to_tmp 把上传的 MP4 字节落临时目录文件供 ffmpeg 直接读。
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _save_to_tmp(data: bytes, td: str) -> Path:
    """把 MP4 字节落临时文件，让 ffmpeg 直接读。"""
    p = Path(td) / "input.mp4"
    p.write_bytes(data)
    return p


def extract_frames(video: Path, out_dir: Path, fps: int) -> list[Path]:
    """ffmpeg 抽帧 + mpdecimate 去重复帧 + 重采样到目标 fps。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%05d.png"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"mpdecimate,fps={fps}",
        str(pattern),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(out_dir.glob("frame_*.png"))