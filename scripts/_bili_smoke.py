"""Quick live test of the B站 history endpoint.

Usage:
  set BILI_SESSDATA=xxx
  set BILI_EXTRA_COOKIES=buvid3=...; bili_jct=...
  python scripts/_bili_smoke.py

Or hard-code the variables below (NOT recommended; the file is git-tracked).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from rt_backend.bilibili_history.service import fetch_recent_history  # noqa: E402
from rt_backend.core.http import HttpClientHolder  # noqa: E402

# ====== 从环境变量读取（推荐） ======
SESSDATA = os.environ.get("BILI_SESSDATA", "")
EXTRA = os.environ.get("BILI_EXTRA_COOKIES", "")

if not SESSDATA:
    print("ERROR: 请设置环境变量 BILI_SESSDATA", file=sys.stderr)
    print("  PowerShell: $env:BILI_SESSDATA='xxx'", file=sys.stderr)
    print("  bash:       export BILI_SESSDATA=xxx", file=sys.stderr)
    sys.exit(1)


async def main() -> None:
    holder = HttpClientHolder(timeout=15.0)
    await holder.start()
    try:
        items, pages = await fetch_recent_history(
            http=holder,
            sessdata=SESSDATA,
            extra_cookies=EXTRA or None,
            days=7,
            business="all",
            max_pages=3,
        )
        print(f"pages={pages}, items={len(items)}")
        print("--- 前 5 条 ---")
        for it in items[:5]:
            print(
                f"{it.view_at_iso}  bvid={it.bvid}  tag={it.tag_name}  "
                f"prog={it.progress}/{it.duration}s  {it.title[:30]}"
            )
        print("--- 全部按 tag 聚合 ---")
        from collections import Counter
        c = Counter(it.tag_name for it in items if it.tag_name)
        for tag, n in c.most_common(15):
            print(f"  {n:3d}  {tag}")
    finally:
        await holder.close()


if __name__ == "__main__":
    asyncio.run(main())
