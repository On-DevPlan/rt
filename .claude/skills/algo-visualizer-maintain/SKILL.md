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
       │ 输出 JSON + 生成 index.json
       ▼
src/modules/algorithm/data/<algo-id>.json
src/modules/algorithm/data/index.json    ← 算法索引（静态导入）
       │
       ▼ (动态加载 via import.meta.glob)
src/modules/algorithm/pages/AlgoVisualizerPage.jsx
       │
       ├── 算法选择器（顶栏 dropdown）
       │   ├── 读取 index.json 列出所有算法
       │   └── 选中后动态 import 对应 JSON 文件
       │
       ├── CodeDisplay 组件
       │   ├── computeLineDiff()     ← 行级 diff（前缀/后缀匹配）
       │   ├── 打字机动画逐行播放     ← 32ms/字符，280ms 行间停顿
       │   └── 'same' 行始终使用 codeHtml[] 渲染
       │
       ├── AlgorithmVisualization 组件
       └── ExplanationPanel 组件
       │
       ▼ 部署
Dockerfile → nginx → 浏览器
```

## 模块结构

```
src/modules/algorithm/
├── module.meta.js                          # 模块注册（路由 /algo/visualizer）
├── data/
│   ├── index.json                          # 算法索引（自动生成，静态导入）
│   ├── two-sum.json                        # 各算法数据（自动生成，动态导入）
│   ├── majority-element.json
│   ├── merge-sorted-array.json
│   └── ...                                 # 新增 TOML 后自动生成
├── pages/
│   ├── AlgoVisualizerPage.jsx              # 主页面
│   └── AlgoVisualizerPage.module.css       # 样式（深色霓虹主题）
public/algos/
│   ├── two-sum.toml                        # 算法定义源文件
│   ├── merge-sorted-array.toml
│   └── ...                                 # 直接添加即可
scripts/
│   └── parse_algo.py                       # TOML → JSON 解析器
```

## 添加新算法

**三步完成，无需改前端代码：**

1. 在 `public/algos/` 下创建 `<algo-id>.toml`
2. 运行 `pnpm parse:algos`（自动生成 JSON + 更新 index.json）
3. 运行 `pnpm run build`（Vite 自动察觉新 JSON 文件）

前端使用 `import.meta.glob('../data/*.json')` 动态加载，新文件会自动出现在顶栏下拉菜单中。

### 1. 创建 TOML

在 `public/algos/` 下创建 `<algo-id>.toml`，格式见 [`docs/algo-toml-spec.md`](../../../docs/algo-toml-spec.md)：

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
- **高亮**: `'same'` 行**始终**使用 `codeHtml[]` 语法高亮 HTML（不受动画状态影响），'add'/'del' 行在动画完成后替换为 HTML
- **步骤过渡**: 组件保持挂载（不使用 `key` 强制重建），`code`/`prevCode` 变化时 diff 引擎自动计算新旧差异并驱动打字机动画，无 Remount 闪烁

### ExplanationPanel（说明区）

- 组件保持挂载，`step`/`current` prop 变化时内容直接更新
- `mdToHtml()` 内联 Markdown 渲染器（无外部依赖），支持表格/代码块/引用/列表

### AlgorithmVisualization（可视化区）

- 根据 `step.visualizationType` 渲染不同可视化组件
- 组件：`ArrayVisualizer`（数组方块）、`MapVisualizer`（哈希表）、`ResultVisualizer`（结果徽章）

## 主题系统

CSS 变量在 `AlgoVisualizerPage.module.css` 的 `:root` 中定义：

```css
--algo-bg: #181818;        /* 主背景（深灰黑） */
--algo-surface: #181818;   /* 面板背景（同主背景） */
--algo-surface2: #1a1a1a;  /* 次级面板（略浅） */
--algo-cyan: #00f0ff;      /* 主色调（关键字、高亮） */
--algo-pink: #ff6b9d;      /* 副色调（装饰器、self） */
--algo-green: #00ff87;     /* 成功/字符串 */
--algo-amber: #ffd93d;     /* 函数名/数字 */
```

**字体大小**（`AlgoVisualizerPage.module.css`）：
- 代码区：`font-size: 19px`（`.codeBlock`）
- 行号：`font-size: 15px`（`.lineNumber`）

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
| 用 `fadeKey` + React `key` 强制组件重建实现步骤切换 | 面板卸载重建导致刷新闪烁 + CSS remount 动画重播 | 移除 fadeKey，组件保持挂载，让 diff 引擎自然响应 prop 变化 |
| 步骤切换后 'same' 行先渲染纯文本，动画开始后才切 HTML | 纯文本→语法高亮的渲染切换导致闪烁 | `'same'` 行不受动画状态控制，始终直接渲染语法高亮 HTML |
| 右侧/下方面板缺 `flex: 1` | 面板只占内容宽度，剩余空白 | 必须加 `flex: 1` |
| 水平分隔条拖动方向符号写反 | 向下拖分隔条，可视区反而变大 | `startPx - dy`（分隔条在可视区上方） |
| 拖动时全局 `cursor: col-resize` | 水平分隔条鼠标指针也变成左右拖动 | 用 `.page.dragging .leftPanel { cursor: col-resize }` 精准设置，不要用 `.page.dragging *` 全局通配 |
| `_audit.cjs` 不在 `scripts/` 目录运行 | 路径解析错误，报告找不到文件 | 必须 `cd scripts && node _audit.cjs` |

## 可拖拽面板布局

AlgoVisualizerPage 支持两个维度的拖拽调整：

```
┌─────────────────┬─┬─────────────────┐
│   代码区 (flex:1) │ │                 │
├───────────────── ║ ├─────────────────┤
│ 可视化区 (height) ║ │   右侧说明面板   │
│  ↑ 水平分隔条可拖拽│ │   (flex:1)     │
└─────────────────┴─┴─────────────────┘
          ↑ 垂直分隔条可拖拽
```

**CSS 关键规则**：

| 面板 | 必需属性 | 说明 |
|------|---------|------|
| 左/上面板 | `width: N%`（JS 控制） | 不要写死 flex 数字 |
| 右/下面板 | `flex: 1` | 自动填满剩余空间（易遗漏！） |
| 分隔条 | `flex-shrink: 0` | 防止被压缩 |

**拖拽方向公式**：
- 水平分隔条（上下调整）：`startPx - dy`（向下拖 dy>0 → 可视区减小）
- 垂直分隔条（左右调整）：`startPct + (dx / containerW) * 100`

## 待办

- [x] **算法列表切换**：顶栏 dropdown + `import.meta.glob` 动态加载，新增 TOML 文件后自动发现
- [x] **可拖拽面板布局**：左侧代码/可视区、左右侧面板均支持拖拽调整大小（垂直+水平双分隔条）
- [x] **代码区字体增大**：代码 17px、行号 14px
- [ ] **自适应动画速度**：当前固定 32ms/字符，短行过快长行过慢，应基于行长度动态调整
- [ ] **可视化数据自动化**：`visualizationData` 已手动维护，应用 Python 运行测试 case 自动生成
- [ ] **复杂 diff 增强**：当前前缀/后缀算法不支持行内修改检测，可用 Myers diff 改进
- [ ] **后端 TTS 服务**：运行时需要 uvicorn 进程，若部署时后端未启动不影响前端

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
