# Reading TTS 单词级阅读功能设计

## 概述

为 src/modules/reading 添加 edge_tts 单词级精确定位功能，部署在 Docker 单一容器内。

## 架构

```
Docker 容器 (nginx:80 + python:8080)
├── nginx:80
│   ├── /tts/* → 反向代理到 python:8080
│   └── /       → 静态文件
└── python:8080 (supervisord)
    └── edge_tts + WordBoundary API
```

## 目录结构

```
src/
├── modules/reading/
│   ├── pages/
│   │   ├── SentenceReaderPage.jsx      # 页面
│   │   └── SentenceReaderPage.module.css
│   ├── hooks/
│   │   └── useTTS.js                  # 播放状态管理
│   ├── services/
│   │   └── ttsApi.js                  # 调用后端 API
│   └── utils/
│       └── wordHighlighter.js          # 单词高亮逻辑

tts/                                       # Python 后端
├── tts_server.py
├── requirements.txt
└── supervisord.conf

Dockerfile
docker-compose.yml
default.conf
supervisord.conf
```

## API 设计

### POST /tts_with_timing
- Request: `{ text, voice, rate, pitch }`
- Response: `{ audio: base64, words: [{text, offset, duration}], cached }`

### POST /tts
- 流式 TTS，返回音频块

## 前端模块

| 模块 | 职责 |
|-----|------|
| `useTTS` | 管理播放状态、当前词索引 |
| `ttsApi` | 调用后端获取音频+时间戳 |
| `wordHighlighter` | 根据播放时间计算当前词 |

## 部署

- Docker 容器内运行 nginx + python
- supervisord 管理 Python 进程
- nginx 反向代理 /tts/* 到 python:8080
