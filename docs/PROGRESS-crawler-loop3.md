# 爬虫模块差距补全循环 — loop-3 进度文件

> Ralph 循环 loop-3（5 轮，无完成承诺）。每轮协议：sub agent 差距分析 →
> 实现 1-3 个最高价值项 → pytest 全绿 + build → 更新本文件 → commit。
> 前置成果：docs/PROGRESS-crawler-loop2.md（loop-2，已完结 299 测试）

## 状态

| 轮次 | sub agent 报告 | 实现项 | 验证 | commit |
|---|---|---|---|---|
| 1 | ✅ 14 条差距（0 高/6 中/8 低；三桶：生产加固/功能完备/文档测试对齐） | G7 WBI key 缓存 + G11 服务层单测补齐（bilibili_tools/mediacrawler） | ✅ 322/0 + build | ✅ |
| 2 | ✅ 11 条遗留验证（G3 修正：-503 是 HTTP 200 envelope，request_with_retry 看不见）+ 新增 N1-N4（WBI 缓存失效缺失/WeakKeyDictionary/锁粒度/时钟） | G3 favorites/add 节流+限流重试+部分结果保留 + N1/N2/N4 WBI 失效换 key 重试 + G10 cookbook §3.8/§3.9 | ✅ 328/0 + build | ✅ |
| 3 | ✅ 8 条遗留全复核 + 前端 specs 同步检查（端点↔卡片 16/16 全覆盖）+ e2e 缺口盘点（bilibili-tools 1/5、bilibili-crawler 2/8） | G2 歌曲列表截断可感知（page_count+truncated）+ G12 limit_hit + e2e 补齐（风控换 key/favorites-add/音频三件套/mediacrawler 前缀） | ✅ 332/0 + build | ✅ |
| 4 | ✅ G6/G4/G5/G1/G8/G9 全复核（两处修正：is_cooperation 在 View.rights；pub_time 在 module_author 且无 view 字段只有 stat.play）+ 6 处 stale 文档定位 | G6 play-url 补 timelength+support_formats + G5 user-space 补 pub_time/pub_ts/play + G1 魔法 mid 注释 + 6 处 stale 文档修复 | ✅ 332/0 + build | ✅ |
| 5 | ✅ 收官检查：4 个 README 路由表 ↔ 路由器全一致（8/5/1/2）、cookbook §1 对 16 端点 GET/POST 全对、前端单模块结构 PASS、无 closure blocker；landing 页 3 处 stale 数字（13→16、×6→×9）+ G8 判定为 moot | G4 视频详情补 staff/is_cooperation + landing 页数字修正 + G9 .md 截断对齐 2000 + 进度清单同步 | ✅ 332/0 + build | ✅ |

**loop-3 收官结论**：迁移闭环完成。332 测试全绿 + build 通过；4 模块 README 路由表与实现一一对应；
cookbook §3.1-§3.9 全部端点/字段为最新；前端 16 端点卡片与路由器 1:1；遗留仅 G13（评论 wbi
变体，维持文档化决策）与 /x/space/fav/arc 兼容开关（低优先 backlog）。
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

## 第 1 轮记录（2026-10-11）

**sub agent 报告结论**（14 条差距，三桶）：
- 生产加固：G7 WBI key 每请求重取 nav（慢 + 风控）、G3 favorites/add 无重试无节流、G1 song_info 魔法 mid=8047632
- 功能完备：G2 audio max_pages 服务端硬编码默认 3、G6 play-url 缺 support_formats/timelength、G13 评论可用 wbi 变体、G4 视频详情缺 staff、G5 user-space 缺 pub_time/view
- 文档测试对齐：G11 bilibili_tools/mediacrawler 服务层单测缺失、G10 cookbook 缺 favorites/add + wbi/sign 场景、G12 skill_seekers 50 页上限未暴露 limit_hit、G9 code_samples 截断未文档化、G8 全域 BFS 无警告

**本轮实现**（G7 + G11）：

1. **G7 WBI key 缓存**（`bilibili_crawler/service.py`）：
   - `_wbi_cache: dict[int, tuple[float, str, str]]` 按 `id(client)` 缓存，TTL 3600s
   - `asyncio.Lock` 双重检查锁（lock 后再查缓存，防并发重复取）
   - mediacrawler search 复用 `sign_params`，同样受益
2. **G11 服务层单测补齐**：
   - `tests/unit/test_bilibili_tools_service.py` 新建 21 断言：fav_mlid 数学（文档已知向量 686127×100+…=1052622027）、parse_fav_link（标准/多参数/缺 fid/缺 mid）、parse_audio_sid / parse_menu_sid / parse_space_uid（完整 URL/裸 id/无匹配）
   - `tests/unit/test_mediacrawler_service.py` 新建：_strip_highlight 5 用例（keyword/带属性/无标签/多标签/空串）
   - `tests/unit/test_bilibili_crawler_service.py` +2 缓存用例：同 client 二次调用命中缓存（nav_calls==1）、不同 client 各自独立缓存
3. 文档同步：`bilibili_crawler/README.md` WBI 行注明 1 小时缓存语义

**验证**：backend pytest **322 passed / 0 failed**（+23）；`pnpm build` 通过。

**下轮候选**（按 sub agent 价值序）：G3 favorites/add 重试+节流（medium）、G2 audio max_pages 提升默认 + 上限、G10 cookbook 补 favorites/add + wbi/sign 场景、G12 limit_hit 暴露。

## 第 2 轮记录（2026-10-11）

**sub agent 报告结论**：11 条遗留全部复核；关键修正：G3 的 -503/-509 以 HTTP 200 envelope 到达，
request_with_retry（HTTP 状态码层）看不见，必须按 envelope code 重试；G12 半失效（cookbook 已写
50 页上限，只差 limit_hit 字段）；新增 N1（WBI key 无失效路径——服务端轮转后最长 1h 全部 502）、
N2（id() 键缓存应换 WeakKeyDictionary）、N4（锁后重取时钟）。

**本轮实现**（G3 + N1/N2/N4 + G10）：

1. **G3 favorites/add 加固**（`bilibili_tools/service.py`）：
   - 节流：相邻 aid 间隔 `_FAV_ADD_THROTTLE=0.3s`（模块常量可测）
   - 限流重试：envelope `-503/-509` 按 `_FAV_ADD_RETRY_DELAYS=(0.5,1.5)` 退避重试（最多 3 次尝试）
   - 部分结果保留：单条网络错误落 `pattern=-1` 条目，不再丢失整批已完成结果；传输层接 `request_with_retry`
2. **N1/N2/N4 WBI 缓存失效**（`bilibili_crawler/service.py` + `mediacrawler/service.py`）：
   - 新 `RiskControlError(UpstreamError)`：HTTP 412 与 envelope -352/-403/-412 语义化（沿用 502 映射）
   - `invalidate_wbi_keys(client)` + `_signed_get_json`：风控即失效缓存换 key 重试一次
   - fetch_play_url / fetch_user_videos / mediacrawler search 全部接线
   - `_wbi_cache` 换 `WeakKeyDictionary`（client GC 条目随灭，杜绝 id 复用脏读）；锁后重取时钟
3. **G10 cookbook**：新增 §3.8 批量收藏一条龙（含 pattern 码表解读）、§3.9 WBI 签名调试
4. **测试 +6**：-503→0 重试成功 / -509 耗尽落 pattern=2 / 批量中途网络错误保留部分结果 /
   换 key 重试成功（nav×2,api×2）/ 耗尽风控抛 RiskControlError / invalidate 后强制重取
5. **测试基建**：`core/http.py` 抽模块级 `_sleep` 符号——sleep_calls fixture 只 patch 它，
   不再污染全局 asyncio.sleep（修复与 e2e uvicorn 线程跨线程串扰的偶发 fail）

**验证**：backend pytest **328 passed / 0 failed**（+6），12.2s；`pnpm build` 通过。

**下轮候选**：G2 audio 列表截断可感知（total=pageCount + truncated 标志）、G12 limit_hit、
G6 support_formats/timelength、G1 魔法 mid 文档化。

## 第 3 轮记录（2026-10-11）

**sub agent 报告结论**：8 条遗留全复核仍有效；前端 specs 与后端 16 端点一一对应无卡片缺口
（仅描述性欠缺：favorites-add 重试语义、menu/user-songs 截断语义）；e2e 结构性缺口最大——
bilibili-tools 仅 1/5 端点、bilibili-crawler 2/8，r1-r2 的两个高价值行为（写路径加固、
风控换 key 重试）都没有 e2e 级回归保护；`test_all_crawler_prefixes_mounted` 漏 /api/mediacrawler。

**本轮实现**（G2 + G12 + e2e 补齐）：

1. **G2 截断可感知**（`bilibili_tools/service.py` + `schemas.py`）：
   - `_fetch_song_list` 返回 `(songs, page_count, truncated)` 三元组（for-else 判定翻满未到最后一页）
   - MenuSongsResponse/UserSongsResponse 新增 `page_count`（上游总页数）+ `truncated`（因 max_pages 截断）
   - 新测试 `test_menu_songs_truncation_flag`（pageCount=3 + max_pages=1 → truncated=true，只打 1 次）
2. **G12 limit_hit**（`skill_seekers/service.py` + `schemas.py`）：ScrapeResponse 新增
   `limit_hit = pages_scraped >= max_pages`，50 页上限触顶不再靠推断
3. **e2e 补齐**（`tests/e2e/test_crawler_modules_e2e.py` +3 用例、1 处修正）：
   - `test_play_url_risk_control_key_refresh_through_real_app`：真实 app 全链路 -352 → 失效缓存
     重签 → 成功（playurl 恰好 2 次；nav 缓存可能被同 session 前序用例预热，断言 ≥1）
   - `test_bilibili_tools_favorites_add_through_real_app`：写操作 -503 → 退避重试 → 成功
   - `test_bilibili_tools_audio_trio_through_real_app`：单曲信息/歌单/UP 主歌曲三端点一次覆盖
   - 前缀断言补 `/api/mediacrawler`
4. **前端 specs 描述同步**：favorites-add（pattern 语义 + 部分结果保留）、menu-songs/user-songs
   （truncated/page_count 解读、uid 纯数字）

**验证**：backend pytest **332 passed / 0 failed**（+4），11.3s；`pnpm build` 通过。

**下轮候选**：G6 play-url support_formats/timelength、G4 视频详情 staff、G5 user-space
pub_time/view、G1 魔法 mid 文档化、G8 BFS 降级警告、G9 code 截断文档化。



## 第 4 轮记录（2026-10-11）

**sub agent 报告结论**：G6/G4/G5/G1/G8/G9 全部复核有效，两处上游字段修正——`is_cooperation`
在 `View.rights`（非 View 顶层）；`pub_time/pub_ts` 在 `module_author`，无字面 `view` 字段
（播放数是 `module_dynamic.major.archive.stat.play` 字符串）。另定位 6 处 stale 文档
（r3 字段上线时 README/cookbook 没跟上）。

**本轮实现**（G6 + G5 + G1 + stale 文档）：

1. **G6**（`bilibili_crawler/service.py` + `schemas.py`）：play-url 响应补 `timelength`（片长 ms）
   + `support_formats[]`（各清晰度 quality/format/new_description/display_desc/codecs 上游透传）——
   DASH 场景（fnval=16/4048）durl 为空时这是唯一有信息量的载荷
2. **G5**（同文件）：user-space items 补 `pub_time`/`pub_ts`（module_author）+ `play`
   （archive.stat.play 字符串转 int；命名与 user-videos 对齐）
3. **G1**（`bilibili_tools/service.py` + README）：魔法 mid=8047632 加注释 + 已知限制条目
4. **stale 文档 6 处**：skill_seekers README 补 limit_hit；bilibili_tools README 两行 audio
   路由补 page_count/truncated；bilibili_crawler README user-videos 补 video_review；
   cookbook §3.5 补 limit_hit、§3.7 补 timelength/support_formats；play-url spec 描述同步
5. **测试**：play-url 载具加 timelength/support_formats 断言；user-space 载具加
   module_author/stat.play 断言（play 字符串→int）

**验证**：backend pytest **332 passed / 0 failed**，11.2s；`pnpm build` 通过。

**下轮候选**（loop-3 收官）：G4 staff/is_cooperation、G8 discovery_degraded、G9 .md 截断对齐、
G13 维持文档化决策——均为低优先，收官轮以全量回归 + 文档终检为主。

## 第 5 轮记录（2026-10-11，收官）

**sub agent 报告结论**：无 closure blocker。4 个 README 路由表与路由器全一致
（bilibili_crawler 8 / bilibili_tools 5 / skill_seekers 1 / mediacrawler 2，含
`/audio/{sid}` 通配路由顺序注记）；cookbook §1 速查表对 16 端点 GET/POST 划分全对；
前端单模块结构 PASS（16 卡片 1:1、无断链）；G8 判定 moot（discovered_via_* 计数
已可推断降级，flag 冗余）；landing 页遗留 3 处 stale 数字（自相矛盾：hero 说 13
端点、卡片合计 16）。

**本轮实现**（G4 + landing 修正 + G9 ride-along）：

1. **G4**（`bilibili_crawler/service.py` + `schemas.py`）：视频详情补
   `is_cooperation`（View.rights.is_cooperation）+ `staff[]`（View 顶层成员
   mid/name/title，新 `StaffMember` 模型）——合作视频归属不再只有 owner
2. **landing 页修正**（`CrawlersHomePage.jsx`）：端点数 13→16（速查表行 + hero），
   场景 ×6→×9 并补全 §3.7/§3.8/§3.9 枚举
3. **G9 ride-along**（`skill_seekers/service.py` + `schemas.py`）：.md 路径
   code_samples 截断对齐 HTML 路径的 2000 字符 + CodeSample.code 注明上限
4. **文档**：README 视频详情行、cookbook §3.7 补 staff/is_cooperation；本文件
   遗留清单同步勾选（G6/G5/G1/G4/G9 完成，G8 moot 关闭）

**验证**：backend pytest **332 passed / 0 failed**，11.5s；`pnpm build` 通过。

## 遗留候选（未实现项，供后续轮次）

- [ ] 收藏夹旧接口 /x/space/fav/arc 兼容开关（loop-1 遗留，低优先）
- [x] ~~G3 favorites/add 重试+节流~~（r2 完成）
- [x] ~~G6 play-url support_formats/timelength~~（r4 完成）
- [ ] G13 评论 wbi 变体端点（维持文档化决策）
- [x] ~~G10 cookbook favorites/add + wbi/sign 场景~~（r2 完成）
- [x] ~~G12 skill_seekers limit_hit 暴露~~（r3 完成）
- [x] ~~G8 全域 BFS 警告~~（r5 判定 moot：discovered_via_* 计数已可推断，关闭）
- [x] ~~G2 audio 列表截断可感知（pageCount/truncated）~~（r3 完成）
- [x] ~~G1 song_info 魔法 mid=8047632 文档化~~（r4 完成）
- [x] ~~G4 视频详情 staff/is_cooperation~~（r5 完成）
- [x] ~~G5 user-space items 补 pub_time/view~~（r4 完成，按上游实态命名 pub_time/pub_ts/play）
- [x] ~~G9 code_samples 截断不对称（HTML 2000 / .md 无上限）~~（r5 完成：.md 对齐 2000 + schema 注明）
