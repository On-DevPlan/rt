# 爬虫模块差距补全循环 — loop-3 进度文件

> Ralph 循环 loop-3（5 轮，无完成承诺）。每轮协议：sub agent 差距分析 →
> 实现 1-3 个最高价值项 → pytest 全绿 + build → 更新本文件 → commit。
> 前置成果：docs/PROGRESS-crawler-loop2.md（loop-2，已完结 299 测试）

## 状态

| 轮次 | sub agent 报告 | 实现项 | 验证 | commit |
|---|---|---|---|---|
| 1 | ✅ 14 条差距（0 高/6 中/8 低；三桶：生产加固/功能完备/文档测试对齐） | G7 WBI key 缓存 + G11 服务层单测补齐（bilibili_tools/mediacrawler） | ✅ 322/0 + build | ✅ |
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

## 遗留候选（loop-2 未实现项）

- [ ] 收藏夹旧接口 /x/space/fav/arc 兼容开关（loop-1 遗留，低优先）
- [ ] G3 favorites/add 重试+节流
- [ ] G6 play-url support_formats/timelength
- [ ] G13 评论 wbi 变体端点
- [ ] G10 cookbook favorites/add + wbi/sign 场景
- [ ] G12 skill_seekers limit_hit 暴露
- [ ] G8 全域 BFS 警告
