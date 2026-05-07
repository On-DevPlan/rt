---
name: gh-ci-remote-debug
description: Use when CI/CD deployment fails and local debugging isn't possible, container crashes on startup, or when logs from GitHub Actions environment are needed to diagnose issues.
---

# GitHub Actions + gh CLI 远程 Debug 模式

## Overview
在 GitHub Actions 环境中复现和诊断 CI/CD 问题，使用 gh CLI 触发和监控 workflow，Monitor 工具追踪状态变化。

## When to Use
- CI/CD 部署失败需要诊断
- 容器启动崩溃但本地无法复现
- 需要 GitHub Actions 环境中的完整日志
- 用户说"debug"、"监控 CI"、"查看日志"、"为什么失败"

## Core Pattern

### 1. 创建 Debug Workflow

```yaml
name: Debug Deploy
on:
  workflow_dispatch:

jobs:
  debug:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # === 根据项目调整：构建依赖 ===
      - name: Setup pnpm
        uses: pnpm/action-setup@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm run build

      # === Docker 构建和启动 ===
      - run: docker compose build

      # ⚠️ 必须设置 timeout 避免资源浪费
      - name: Docker Compose up
        timeout-minutes: 8
        run: docker compose up --abort-on-container-exit

      - name: Show logs on failure
        if: failure()
        run: docker compose logs --tail=100
```

### 2. 触发和监控

```bash
# 触发 workflow
gh workflow run Debug\ Deploy

# 监控状态（⚠️ 关键）
Monitor: gh run view <run_id>
```

### 3. Monitor 正确用法

**绝对规则：Monitor 完成后必须验证状态**

```
Monitor 返回 completed
  → gh run view <run_id> 验证
  → in_progress: 继续等待或重新 Monitor
  → completed/success/failure: 安全读取日志
```

### 4. 获取日志

```bash
# 查看失败日志
gh run view --job=<job_id> --log-failed

# 查看完整日志
gh run view --job=<job_id> --log
```

## Common Mistakes

### 错误 1：Monitor 误判（⚠️ 极其严重）

**错误流程：**
```
Monitor completed → 直接读取 gh run view → 数据过时/不存在
```

**正确流程：**
```
Monitor completed → gh run view <run_id> 验证状态 → 获取日志
```

### 错误 2：忘记设置 timeout

```yaml
- name: Docker Compose up
  timeout-minutes: 8  # ⚠️ 必须设置
  run: docker compose up --abort-on-container-exit
```

## Key Principles

- **Monitor/Loop 是用户特权**：不能主动取消
- **验证优于假设**：workflow 状态以 gh run view 为准
- **永远不要假设** Monitor 返回 = 任务完成

## 错误案例

### 错误：Monitor 完成后未验证状态即读取日志

**错误流程：**
```
Monitor completed → 直接 gh run view --log → 数据不存在或过时
```

**正确流程：**
```
Monitor completed → gh run view <run_id> 验证状态 → 根据状态决定操作
```

### 错误：主动取消 Monitor/Loop

**致命错误：**
```
Monitor 正在追踪状态 → 主动调用 TaskStop 取消 → 丢失监控能力
```

**后果：** 后续 Monitor 工具可能无法正常工作，或返回不准确的状态。

**正确做法：**
- 等待 Monitor 自然结束或状态变化通知
- 如果需要停止，让用户明确知道这是他们的特权
- 永远不要主动取消 Monitor/Loop 工具
