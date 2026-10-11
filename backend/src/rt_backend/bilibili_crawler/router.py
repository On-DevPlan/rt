"""Bilibili crawler HTTP endpoints（前缀 /api/bilibili-crawler）。"""
import datetime
import json
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from ..core.archive import md_table, readme_index, zip_bytes
from ..core.http import HttpClientHolder
from .schemas import (
    CommentsArchiveRequest,
    CommentsRequest,
    CommentsResponse,
    DanmakuResponse,
    IdConvertResponse,
    PlayUrlRequest,
    PlayUrlResponse,
    UserSpaceRequest,
    UserSpaceResponse,
    UserVideosArchiveRequest,
    UserVideosRequest,
    UserVideosResponse,
    VideoInfoResponse,
    WbiSignRequest,
    WbiSignResponse,
)
from .service import (
    AuthError,
    BilibiliCrawlerError,
    UpstreamError,
    av2bv,
    bv2av,
    fetch_comments,
    fetch_danmaku,
    fetch_play_url,
    fetch_user_space,
    fetch_user_videos,
    fetch_user_videos_all,
    fetch_video_detail,
    sign_params,
)


def build_router(http_provider: Callable[[], HttpClientHolder]) -> APIRouter:
    router = APIRouter(prefix="/api/bilibili-crawler", tags=["bilibili-crawler"])

    @router.post("/wbi/sign", response_model=WbiSignResponse)
    async def wbi_sign(
        req: WbiSignRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """对任意参数做 B 站 WBI 签名（实时取 nav 接口的 img/sub key）。"""
        try:
            signed = await sign_params(http.client, dict(req.params))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        wts = int(signed["wts"])
        return WbiSignResponse(
            w_rid=signed["w_rid"],
            wts=wts,
            signed_params=signed,
            query="&".join(f"{k}={v}" for k, v in signed.items()),
        )

    @router.get("/convert", response_model=IdConvertResponse)
    async def convert_id(aid: int | None = None, bvid: str | None = None):
        """av<->bv 互转（纯计算，不访问网络）；两个参数二选一。"""
        if (aid is None) == (bvid is None):
            raise HTTPException(status_code=422, detail="aid 与 bvid 恰好提供一个")
        try:
            if aid is not None:
                return IdConvertResponse(aid=aid, bvid=av2bv(aid))
            return IdConvertResponse(aid=bv2av(bvid), bvid=bvid)
        except (ValueError, IndexError) as e:
            raise HTTPException(status_code=422, detail=f"非法 id：{e}")

    @router.get("/video/{video_id}", response_model=VideoInfoResponse)
    async def video_info(
        video_id: str,
        http: HttpClientHolder = Depends(http_provider),
        sessdata: str | None = None,
    ):
        """视频完整详情（view/detail）：aid 或 bvid 自适应入参，含分P pages[]（每P cid）。"""
        if video_id.startswith("BV"):
            aid, bvid = None, video_id
        elif video_id.isdigit():
            aid, bvid = int(video_id), None
        else:
            raise HTTPException(status_code=422, detail=f"video_id 须为 aid（纯数字）或 bvid（BV 开头）：{video_id!r}")
        try:
            info = await fetch_video_detail(http.client, aid=aid, bvid=bvid, sessdata=sessdata)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return VideoInfoResponse(**info)

    @router.post("/play-url", response_model=PlayUrlResponse)
    async def play_url(
        req: PlayUrlRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """播放直链 + 清晰度枚举（WBI 签名 playurl；aid/cid 从 /video/{id} 的 pages[] 拿）。"""
        try:
            data = await fetch_play_url(
                http.client,
                aid=req.aid,
                cid=req.cid,
                qn=req.qn,
                fnval=req.fnval,
                fourk=req.fourk,
                sessdata=req.sessdata,
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return PlayUrlResponse(**data)

    @router.get("/danmaku/{cid}", response_model=DanmakuResponse)
    async def danmaku(cid: int, http: HttpClientHolder = Depends(http_provider)):
        """分P弹幕（dm/list.so XML → 结构化列表；cid 从 /video/{id} 的 pages[] 拿）。"""
        try:
            data = await fetch_danmaku(http.client, cid)
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return DanmakuResponse(**data)

    @router.post("/comments", response_model=CommentsResponse)
    async def comments(
        req: CommentsRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """两级评论爬取：一级评论分页 + 楼中楼展开，字段与原脚本对齐。"""
        try:
            data = await fetch_comments(
                http.client,
                oid=req.oid,
                type_=req.type,
                ps=req.ps,
                pages=req.pages,
                include_replies=req.include_replies,
                mode=req.mode,
                sessdata=req.sessdata,
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return CommentsResponse(**data)

    @router.post("/user-space", response_model=UserSpaceResponse)
    async def user_space(
        req: UserSpaceRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """UP 主动态列表：抽取每条的 comment_id_str/comment_type（可用于后续爬评论）。"""
        try:
            data = await fetch_user_space(
                http.client, mid=req.mid, max_pages=req.max_pages, sessdata=req.sessdata
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return UserSpaceResponse(**data)

    @router.post("/user-videos", response_model=UserVideosResponse)
    async def user_videos(
        req: UserVideosRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """UP 主全量投稿列表（WBI 签名的 arc/search）——区别于 user-space 的动态子集，
        抓「全部投稿的评论」场景请用本端点拿 (aid, type=1) 对再喂 /comments。"""
        try:
            data = await fetch_user_videos(
                http.client,
                mid=req.mid,
                pn=req.pn,
                ps=req.ps,
                order=req.order,
                sessdata=req.sessdata,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return UserVideosResponse(**data)

    # --- 归档导出：贪心翻页 → zip 下载 --------------------------------------

    def _archive_response(filename: str, data: dict, files: dict[str, str], items_header: int) -> Response:
        payload = dict(files)
        payload["README.md"] = readme_index(
            filename.replace(".zip", "").replace("-", " ").replace(".json", "").replace(".md", ""),
            [(k, v) for k, v in data.items() if k != "items" and not isinstance(v, list)],
            [(name, name.rsplit(".", 1)[-1].upper() + " 数据") for name in files if name != "README.md"],
        )
        return Response(
            content=zip_bytes(payload),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Archive-Items": str(items_header),
            },
        )

    @router.post("/comments/archive")
    async def comments_archive(
        req: CommentsArchiveRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """两级评论贪心爬取 → zip 下载（README.md + comments.json + comments.md）。

        与 /comments 的区别：忽略 pages，翻到上游 is_end 为止（安全上限 max_pages）。"""
        try:
            data = await fetch_comments(
                http.client,
                oid=req.oid,
                type_=req.type,
                ps=req.ps,
                include_replies=req.include_replies,
                mode=req.mode,
                sessdata=req.sessdata,
                greedy=True,
                max_pages=req.max_pages,
            )
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))

        md_lines = [
            f"# 评论归档 {req.oid}（type={req.type}）",
            "",
            f"- 总评论（一级，含置顶）: {data['total']} · 翻页: {data['pages_fetched']} · "
            f"is_end: {data['is_end']} · limit_hit: {data['limit_hit']}",
            "",
        ]
        for c in data["items"]:
            pin = "📌 " if c.get("pinned") else ""
            md_lines += [
                f"## {pin}{c['name']} · {c['time']} · 👍 {c['like']}",
                "",
                c["message"],
                "",
                f"> {c['location']} · Lv{c['level']}",
                "",
            ]
            for r in c.get("replies") or []:
                md_lines += [f"> **↳ {r['name']}** {r['time']} 👍 {r['like']}：{r['message']}", ""]
        day = datetime.date.today().isoformat()
        return _archive_response(
            f"bilibili-comments-{req.oid}-{day}.zip",
            data,
            {
                "comments.json": json.dumps(data, ensure_ascii=False, indent=2),
                "comments.md": "\n".join(md_lines).rstrip() + "\n",
            },
            data["total"],
        )

    @router.post("/user-videos/archive")
    async def user_videos_archive(
        req: UserVideosArchiveRequest,
        http: HttpClientHolder = Depends(http_provider),
    ):
        """UP 主全量投稿贪心爬取 → zip 下载（README.md + videos.json + videos.md）。

        与 /user-videos 的区别：自动翻 pn 到 count 覆盖完（安全上限 max_pn）。"""
        try:
            data = await fetch_user_videos_all(
                http.client,
                mid=req.mid,
                ps=req.ps,
                order=req.order,
                sessdata=req.sessdata,
                max_pn=req.max_pn,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except UpstreamError as e:
            raise HTTPException(status_code=502, detail=str(e))
        except BilibiliCrawlerError as e:
            raise HTTPException(status_code=500, detail=str(e))

        videos_md = md_table(
            ["#", "title", "bvid", "aid", "play", "length"],
            [
                [i + 1, v["title"], v["bvid"], v["aid"], v.get("play"), v.get("length", "")]
                for i, v in enumerate(data["items"])
            ],
        )
        day = datetime.date.today().isoformat()
        return _archive_response(
            f"bilibili-videos-{req.mid}-{day}.zip",
            data,
            {
                "videos.json": json.dumps(data, ensure_ascii=False, indent=2),
                "videos.md": videos_md,
            },
            data["total"],
        )

    return router
