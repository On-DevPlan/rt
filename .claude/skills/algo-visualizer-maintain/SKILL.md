---
name: algo-visualizer-maintain
description: LeetCode 算法可视化模块维护文档 — TOML→Python→React 全链路说明、常见坑点、隐藏 TODO
---

# Algorithm Lab 维护手册

## 概述

`Algorithm Lab`（`/algo/visualizer`）是一个 TOML 驱动的 LeetCode 算法逐步构建动画播放器。用户按步骤观看代码从 0 到 1 的编写过程，左侧是 git-diff 风格代码打字机动画，右侧是步骤说明。

## 数据链路

```
public/algos/<algo-id>.toml
       │
       ▼
scripts/parse_algo.py          ← Python (tomllib + pygments)
       │ 读取 TOML
       │ 用 Pygments 语法着色每行代码 → codeHtml[]
       │ 输出 JSON
       ▼
src/modules/algorithm/data/<algo-id>.json
src/modules/algorithm/data/index.json    ← 算法索引
       │
       ▼ (静态 import)
src/modules/algorithm/pages/AlgoVisualizerPage.jsx
       │ CodeDisplay 组件
       │   - computeLineDiff()     ← 行级 diff（前缀/后缀匹配）
       │   - 打字机动画逐行播放     ← 32ms/字符，280ms 行间停顿
       │   - 完成后使用 codeHtml[] ← dangerouslySetInnerHTML 渲染
       │
       ▼ 部署
Dockerfile → nginx → 浏览器
```

## 模块结构

```
src/modules/algorithm/
├── module.meta.js                          # 模块注册（路由 /algo/visualizer）
├── data/
│   ├── index.json                          # 算法索引（自动生成）
│   └── two-sum.json                        # 示例算法数据（自动生成）
├── pages/
│   ├── AlgoVisualizerPage.jsx              # 主页面（699 行）
│   └── AlgoVisualizerPage.module.css       # 样式（深色霓虹主题）
public/algos/
│   └── two-sum.toml                        # 算法定义源文件
scripts/
│   └── parse_algo.py                       # TOML → JSON 解析器
```

## 添加新算法

### 1. 创建 TOML

在 `public/algos/` 下创建 `<algo-id>.toml`，格式：

```toml
[algorithm]
id = "two-sum"
title = "两数之和"
titleEn = "Two Sum"
difficulty = "easy"
tags = ["array", "hash-table"]
testCase = "nums = [2, 7, 11, 15], target = 9"
expectedOutput = "[0, 1]"

[[algorithm.steps]]
id = 0
title = "理解问题"
titleEn = "Understand the Problem"
code = """# 注释..."""
explanation = "**Markdown** 说明"
visualizationType = "intro"

[[algorithm.steps]]
id = 1
# ...递增的代码
```

### 2. TOML 编写规则

| 规则 | 说明 |
|------|------|
| **代码连续性** | 相邻步骤的代码必须保持公共前缀/后缀一致，不可删除已有行（会导致 diff 错乱） |
| **visualizationType** | 可选值：`intro`, `code-only`, `map-create`, `array-iteration`, `map-add`, `map-found`, `result` |
| **visualizationData** | 不同 visualizationType 需要不同字段（见现有 TOML 示例） |
| **explanation** | 支持 Markdown 子集：`**粗体**`、`` `代码` ``、```` ``` ``` ````、表格、引用、列表 |
| **code 字段** | 使用 TOML 的 `"""` 多行字符串，注意内部的 `"` 需要转义为 `\"` 或替换为中文「」 |

### 3. 解析

```bash
pnpm parse:algos              # 解析全部 → 更新 JSON
pnpm parse:algos:watch        # 监视模式（需要 pip install watchdog）
```

### 4. 构建验证

```bash
pnpm run build
```

## 核心组件说明

### CodeDisplay（代码展示区）

- **输入**: `code`（当前步骤代码）, `prevCode`（上一步代码）, `codeHtml[]`（Pygments 预着色每行 HTML）
- **核心算法**: `computeLineDiff(prevCode, currentCode)` — 公共前缀/后缀匹配，输出 `{type: 'same'|'add'|'del', text}` 数组
- **动画**: 
  - 'add' → 逐字打出（32ms/字符），绿色 `+` 标记
  - 'del' → 反向逐字删除，红色 `-` 标记
  - 'same' → 立即显示（无动画）
  - 行间停顿 280ms
- **高亮**: 行完全显示后，用 `codeHtml[idx]` 替换为 Pygments 着色 HTML

### ExplanationPanel（说明区）

- 延迟 150ms 淡入（`opacity` + `transform` CSS 过渡）
- `mdToHtml()` 内联 Markdown 渲染器（无外部依赖），支持表格/代码块/引用/列表

### AlgorithmVisualization（可视化区）

- 根据 `step.visualizationType` 渲染不同可视化组件
- 组件：`ArrayVisualizer`（数组方块）、`MapVisualizer`（哈希表）、`ResultVisualizer`（结果徽章）

## 主题系统

CSS 变量在 `AlgoVisualizerPage.module.css` 的 `:root` 中定义：

```css
--algo-bg: #0a0e1a;        /* 主背景（深海军蓝） */
--algo-surface: #111827;   /* 面板背景 */
--algo-cyan: #00f0ff;      /* 主色调（关键字、高亮） */
--algo-pink: #ff6b9d;      /* 副色调（装饰器、self） */
--algo-green: #00ff87;     /* 成功/字符串 */
--algo-amber: #ffd93d;     /* 函数名/数字 */
```

语法高亮 token 类用 `:global()` 定义，Pygments 在 build 时生成同名 class：

| CSS class | 用途 | 颜色 |
|-----------|------|------|
| `:global(.tokenKeyword)` | `def`, `for`, `if`, `return` | `#00f0ff` |
| `:global(.tokenBuiltin)` | `print`, `len`, `List` | `#a78bfa` |
| `:global(.tokenFunction)` | 函数调用 | `#ffd93d` |
| `:global(.tokenString)` | 字符串/文档字符串 | `#00ff87` |
| `:global(.tokenComment)` | 注释 | `#8b949e` 斜体 |
| `:global(.tokenNumber)` | 数字 | `#ffd93d` |
| `:global(.tokenDecorator)` | `@staticmethod` | `#ff6b9d` 斜体 |
| `:global(.tokenSelf)` | `self`, `cls` | `#ff6b9d` |

## 错误案例

| 错误操作 | 后果 | 正确做法 |
|---------|------|---------|
| TOML 步骤间代码不一致（如 step2 有 JSDoc 而 step3 删掉了） | diff 产生大量删除+新增行，动画错乱 | 相邻步骤保持公共前缀/后缀一致 |
| Dockerfile 中 `COPY dist` 在 `apt-get install nginx` 之前 | nginx 默认 index.html 覆盖前端文件 | 先装 nginx 再复制前端文件 |
| 前端自定义 JS tokenizer | 边缘 case 多（f-string、多行字符串等），难以维护 | 用 Pygments 在 build 时预着色 |
| `explanation` 中使用中文 `""` 引号 | TOML 解析器将 `"` 视为字符串结束符 | 用 `「」` 或转义 `\"` |
| GBK 编码的 Windows 终端运行 python 脚本 | UnicodeEncodeError | 设置 `PYTHONIOENCODING=utf-8` 或 `sys.stdout.reconfigure()` |

## 隐藏 TODO / 未来改进

### 短期

- [ ] **算法列表**：当前只有一个算法（Two Sum），需要在页面内加切换器或侧边栏
- [ ] **搜索/筛选**：通过 `index.json` 实现按难度、标签过滤
- [ ] **自适应动画速度**：当前固定 32ms/字符，短代码行过快，长代码行过慢，应基于行长度动态调整
- [ ] **快捷键提示**：页面顶部 `← →` 和 `Space` 提示不够醒目，新手可能不知道
- [ ] **watch 模式依赖**：`pnpm parse:algos:watch` 需要 `pip install watchdog`，文档未说明

### 中期

- [ ] **多语言支持**：解析器中切换 `PythonLexer()` → `JavaLexer()` / `CppLexer()`，TOML 中加 `language` 字段
- [ ] **算法进度持久化**：用 localStorage 记住用户看过的步骤
- [ ] **移动端适配**：当前左 60%/右 40% 双栏布局在手机上不可用
- [ ] **可视化数据自动化**：`visualizationData` 目前需要手动在 TOML 中维护，应该用 Python 运行测试 case 自动生成
- [ ] **复杂 diff 增强**：当前前缀/后缀算法不支持行内修改检测（修改视为删除+新增），可用 Myers diff 改进

### 长期

- [ ] **LeetCode API 集成**：直接从 LeetCode 抓取题目描述和测试用例
- [ ] **代码执行**：集成 Python sandbox 让用户看到算法真实输出
- [ ] **社区算法库**：用户可上传自己的 TOML 算法定义
- [ ] **对比模式**：同时播放两种算法（如哈希表法 vs 暴力法）对比
- [ ] **单元测试**：parser 和前端组件均无测试
- [ ] **CI 自动生成**：算法 JSON 数据应 CI 时自动生成而非提交到仓库

## 开发命令

```bash
pnpm dev              # 开发服务器（port 81）
pnpm run build        # 生产构建
pnpm parse:algos      # 解析所有 TOML → JSON
pnpm parse:algos:watch  # 监视模式（pip install watchdog）

# Docker
docker build -t rt:latest .
docker run -d --name rt_app -p 81:80 rt:latest
```

## 部署流水线

GitHub Actions (`.github/workflows/deploy.yml`)：

```
push → pnpm build → docker build → SCP to server → docker run
```

已知注意点：
- Dockerfile 中 `COPY --from=frontend` 必须在 `apt-get install nginx` **之后**
- 健康检查通过 `/health`（nginx 直返 `200 ok`）和 `/api/tts/with-timing`
- 后端依赖 supervisor 管理 uvicorn 进程

## 关键文件速查

| 文件 | 行数 | 职责 |
|------|------|------|
| `scripts/parse_algo.py` | 249 | TOML 解析 + Pygments 着色 |
| `AlgoVisualizerPage.jsx` | 699 | 完整前端逻辑 |
| `AlgoVisualizerPage.module.css` | ~350 | 所有样式 |
| `two-sum.toml` | ~120 | 算法数据定义 |
| `Dockerfile` | 35 | 构建+部署 |
| `nginx.conf` | 46 | nginx 配置 |
