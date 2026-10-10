# bilibili_tools — B 站工具集 API

**API 前缀**：`/api/bilibili-tools`　**来源仓库**：`.claude/repo/BilibiliTools`

## 功能作用

把 BilibiliTools 仓库四个核心工具包装成 HTTP 服务：

| 能力 | 原工具 | 本模块实现 |
|---|---|---|
| 收藏夹视频枚举 | `BilibiliGetFavorite/BiliFavDownLd.py` | `service.py: fetch_favorites`——现代化为 v3 接口 `/x/v3/fav/resource/list`（原 ps=1 逐页 → ps≤20 分页按 `has_more` 停止；media_id= fid×100+mid 尾号）；私有/无权限（11004/11010/53013/-403）→ 403 |
| 批量添加收藏 | `BiliBiliAddFavorite/AutoAddFav.py`（含结果码表） | `service.py: add_favorites`，逐个 av 返回 pattern 结果 |
| 歌曲信息 + 播放 CDN | `BilibiliAudioGet.py` 的 `songDownloader` | `service.py: fetch_song_info`（BilibiliClient UA 的 url 接口） |
| 歌单/UP 主歌曲列表 | 同文件 `playlistDownloader` / `userDownloader` | `service.py: fetch_menu_songs / fetch_user_songs`，按 pageCount==curPage 停止翻页 |

**设计决策**：原脚本把内容下载到本地文件（you-get/aria2/`os.system`）的部分**不进 API**——
接口返回元数据与 CDN 直链，下载动作交给调用方。批量收藏是写操作，需要调用方显式传
`SESSDATA + bili_jct`。

## 路由表

| 方法 | 路径 | 参数 | 响应 |
|---|---|---|---|
| GET | `/favorites` | query: `link`（完整收藏夹链接）或 `mid`+`fid`；`limit≤200` | `{mid, fid, total, items:[{aid,title,pic,state}]}` |
| POST | `/favorites/add` | body: `{sessdata, bili_jct, fid, aids[]}` | 逐个 av 的 `{code, ok, pattern, message}` |
| GET | `/audio/playlist/{sid}` | 路径: `am{id}` 或纯数字；`max_pages≤10` | `{menu_sid, total, items:[{sid,title,author,...}]}` |
| GET | `/audio/user` | query: `uid` 或 `link`（space 链接）；`order`、`max_pages` | `{uid, total, items:[...]}` |
| GET | `/audio/{sid}` | 路径: `au{id}` 或纯数字；query: `quality 0-2` | 歌曲信息 + `cdns[]` 直链 |

注意：`/audio/{sid}` 是通配路由，必须注册在 `/audio/playlist`、`/audio/user` 之后（FastAPI 按注册顺序匹配）。

错误映射：`-101/-111` → 401；私有收藏夹 → 403；其他非 0 code → 502。

## curl 案例

```bash
# 1. 收藏夹枚举（直接给链接）
curl "http://127.0.0.1:8080/api/bilibili-tools/favorites?link=https://space.bilibili.com/42/favlist?fid=12345&limit=50"
# → {"mid":"42","fid":"12345","total":30,"items":[{"aid":"111","title":"...","pic":"http://...","state":0}]}

# 2. 批量收藏（写操作，凭证自备）
curl -X POST "http://127.0.0.1:8080/api/bilibili-tools/favorites/add" \
  -H "Content-Type: application/json" \
  -d '{"sessdata":"...","bili_jct":"...","fid":"12345","aids":["170001","2"]}'
# → {"fid":"12345","requested":2,"ok_count":2,"results":[
#      {"aid":"170001","code":"0","ok":true,"pattern":0,"message":"收藏成功"},
#      {"aid":"2","code":"11007","ok":true,"pattern":0,"message":"你已经收藏过该视频！"}]}

# 3. 歌单歌曲列表（支持 am 链接 id）
curl "http://127.0.0.1:8080/api/bilibili-tools/audio/playlist/am76105"
# → {"menu_sid":"76105","total":100,"items":[{"sid":"1","title":"...","author":"..."}]}

# 4. UP 主上传的歌曲（给 space 链接也行）
curl "http://127.0.0.1:8080/api/bilibili-tools/audio/user?link=https://space.bilibili.com/2932528/audio"
# → {"uid":"2932528","total":30,"items":[{"sid":"9","title":"...","author":"..."}]}

# 5. 单曲信息 + CDN 直链（拿直链后自行下载）
curl "http://127.0.0.1:8080/api/bilibili-tools/audio/au241921?quality=2"
# → {"sid":"241921","title":"...","author":"...","lyric":"http://....lrc","cdns":["http://cdn.../song.m4a"]}
```

## 测试

```bash
cd backend && uv run pytest tests/test_bilibili_tools_router.py -v
```

上游接口全部用 respx 拦截（不依赖外网与真实 cookie）。

## 已知限制

- 收藏夹响应在原字段（aid/title/pic/state）上补充了 `bvid` 与收藏夹标题 `fav_title`；`state=1` 表示已失效视频（medias[].attr bit0）
- 音频 CDN 直链有时效与 Referer 校验，客户端下载时需带 B 站 Referer
- 批量收藏单次上限 100 个 av 号
