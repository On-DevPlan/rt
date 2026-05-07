---
name: minimax-tts-research
description: 当用户询问 MiniMax TTS 能力对比、edge_tts vs MiniMax、单词时间戳支持、语音合成边界、minimax tts 能做单词高亮吗等问题时触发。研究 MiniMax 语音合成的 API 能力和限制，为技术选型提供决策依据。
---

# MiniMax TTS 能力与边界研究

## 核心结论速查

| 能力 | edge_tts | MiniMax TTS | 结论 |
|------|----------|-------------|------|
| **单词级时间戳** | ✅ WordBoundary | ❌ 仅句子级 | **根本差异** |
| 流式传输 | ✅ | ✅ | 持平 |
| 音色克隆 | ❌ | ✅ | MiniMax 独有 |
| 情绪渲染 | ❌ | ✅ speech-2.8-hd | MiniMax 独有 |
| 费用 | 免费 | 按量计费 | edge_tts 优 |

## MiniMax 时间戳粒度

**文档明确：** 异步语音合成时间戳返回**精确到句**，不是词。

**验证命令：**
```bash
mmx speech synthesize --text "Hello world" --subtitles --out test.mp3
cat test.srt
```
输出：
```
1
00:00:00,000 --> 00:00:01,084
Hello world
```

## 职责边界决策树

```
需要单词级进度高亮？
    ├─ 是 → edge_tts（唯一选择）
    └─ 否 → 继续判断
        ├─ 需要音色克隆/数字人？
        │   └─ 是 → MiniMax
        └─ 需要流式播放+句子字幕+情绪渲染？
            └─ 是 → MiniMax
        └─ 免费方案？
            └─ 是 → edge_tts
```

## Workaround（必须用 MiniMax 但需要单词级）

1. 前端按单词数量平均分配句子时长
2. ASR 二次处理（成本高）
3. 混合：MiniMax TTS + edge_tts 时间戳

## 常见错误认知

| 错误 | 实际 |
|-----|------|
| MiniMax 有单词时间戳 | ❌ 只有句子级 SRT |
| --subtitles 返回每个单词 | ❌ 返回字幕行 |

## 参考

- 项目：daily-slow-english（Jarrettluo）
- edge_tts 实现：tts_server.py 第172-189行
