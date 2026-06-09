# Algorithm Lab — TOML 数据驱动规范 v1

## 概述

`Algorithm Lab` 采用 **TOML → Python(Pygments) → JSON → React** 的纯数据驱动架构。
算法步骤、代码内容、可视化状态全部在 TOML 中声明，前端按 spec 渲染，零胶水代码。

```
public/algos/<algo-id>.toml
       │ 编写算法定义（本规范）
       ▼
scripts/parse_algo.py   ← Python 解析器
       │ 读取 TOML
       │ Pygments 语法着色 → codeHtml[]
       │ 校验 + 结构转换
       ▼
src/modules/algorithm/data/<algo-id>.json  ← 前端消费
```

---

## 1. 顶层结构

```toml
[algorithm]
# ... 算法元信息（见 §2）

[[algorithm.steps]]
# ... 步骤定义（见 §3），一个文件可以包含 N 个 steps

[algorithm.summary]
# ... 复杂度总结（见 §4），可选
```

---

## 2. `[algorithm]` — 算法元信息

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | `string` | **是** | — | 唯一标识符，用作文件名和数据 key |
| `title` | `string` | **是** | — | 中文标题 |
| `titleEn` | `string` | 否 | `""` | 英文标题 |
| `difficulty` | `string` | 否 | `"medium"` | 难度：`"easy"` / `"medium"` / `"hard"` |
| `tags` | `string[]` | 否 | `[]` | 分类标签，如 `["array", "hash-table"]` |
| `testCase` | `string` | 否 | `""` | 示例测试用例，纯展示用 |
| `expectedOutput` | `string` | 否 | `""` | 预期输出，纯展示用 |

**示例：**

```toml
[algorithm]
id = "two-sum"
title = "两数之和"
titleEn = "Two Sum"
difficulty = "easy"
tags = ["array", "hash-table"]
testCase = "nums = [2, 7, 11, 15], target = 9"
expectedOutput = "[0, 1]"
```

---

## 3. `[[algorithm.steps]]` — 步骤定义

每个步骤代表代码从一个状态到下一个状态的渐进变化。

### 3.1 通用字段

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | `int` | 否 | 从 0 递增 | 步骤编号 |
| `title` | `string` | **是** | — | 步骤中文标题 |
| `titleEn` | `string` | 否 | `""` | 步骤英文标题 |
| `code` | `string` | **是** | — | 当前步骤的完整 Python 代码（TOML 多行字符串） |
| `explanation` | `string` | **是** | — | Markdown 格式的步骤说明 |
| `visualizationType` | `string` | 否 | `"code-only"` | 可视化布局类型，见 §3.2 |
| `visualizationData` | `table` | 否 | `{}` | 可视化数据，不同 `visualizationType` 需要不同字段，见 §3.3 |

### 3.2 `visualizationType` 枚举

| 类型 | 用途 | 布局 |
|------|------|------|
| `"intro"` | 题目介绍，无代码逻辑 | 居中提示文字 |
| `"code-only"` | 仅展示代码结构 | 小提示图标 |
| `"map-create"` | 初始化哈希表 | 数组 + 空 Map |
| `"array-iteration"` | 遍历数组，查找补数 | 数组 + Map + complement 徽章 |
| `"map-add"` | 将元素存入哈希表 | 数组 + Map + 插入操作提示 |
| `"map-found"` | 找到匹配结果 | 数组(高亮) + Map + 成功提示 |
| `"result"` | 最终结果展示 | 数组(高亮) + Map + 结果徽章 |

### 3.3 `visualizationData` 字段对照表

| visualizationType | 必需字段 | 可选字段 | 说明 |
|-------------------|----------|----------|------|
| `intro` | — | — | 无需数据 |
| `code-only` | — | — | 无需数据 |
| `map-create` | `mapContents`, `arrayState` | `currentIndex` | 展示初始空 Map |
| `array-iteration` | `mapContents`, `arrayState`, `currentIndex` | `currentValue`, `complement`, `found` | 展示当前遍历状态 |
| `map-add` | `mapContents`, `arrayState`, `currentIndex`, `mapKey`, `mapValue` | — | 展示元素加入 Map |
| `map-found` | `mapContents`, `arrayState`, `currentIndex`, `complement`, `foundIndex` | `currentValue`, `result` | 展示匹配成功 |
| `result` | `mapContents`, `arrayState`, `result` | `highlightedIndices` | 展示最终结果 |

### 3.4 各字段类型与格式

#### `mapContents` (string)
哈希表当前内容的字符串表示。格式为 `"{key → value, key → value}"`。
- 空表：`"{}"`
- 有数据：`"{2 → 0, 7 → 1}"`

#### `arrayState` (string)
数组内容的字符串表示，与 JavaScript 数组字面量一致。
- 格式：`"[2, 7, 11, 15]"`
- 前端解析：`state.replace(/[\[\]]/g, '').split(', ').map(Number)`

#### `currentIndex` (int)
当前遍历到的数组索引。-1 表示无高亮。

#### `highlightedIndices` (int[])
数组中需要高亮标记的索引列表，如 `[0, 1]`。

#### `complement` (int)
当前元素的补数值（`target - num`），用于展示计算过程。

#### `found` (bool)
`complement` 是否在 Map 中找到。
- `true`（TOML 布尔）→ 显示「✓ 命中!」
- `false` → 显示「未找到」

#### `foundIndex` (int)
在 Map 中找到的匹配索引。

#### `mapKey` / `mapValue` (int 或 string)
正在插入 Map 的键和值。

#### `result` (string)
返回结果字符串，如 `"[0, 1]"`。

---

## 4. `[algorithm.summary]` — 复杂度总结（可选）

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `timeComplexity` | `string` | 否 | `""` | 时间复杂度说明 |
| `spaceComplexity` | `string` | 否 | `""` | 空间复杂度说明 |
| `approach` | `string` | 否 | `""` | 算法思路概述 |
| `keyInsight` | `string` | 否 | `""` | 核心启发/学习点 |

---

## 5. 关键约束

### 5.1 代码连续性（最重要的约束）

相邻步骤的 `code` 字段**必须保持公共前缀和后缀一致**。diff 引擎使用前缀/后缀匹配算法，不支持检测行内修改。

**正确做法** — 每次只增不改：
```
Step 1: "a\nb\nc"     →  前缀匹配: a/b → 后缀匹配: c
Step 2: "a\nb\nX\nc"  →  diff: same a, same b, add X, same c
```

**错误做法** — 删除或修改中间行：
```
Step 1: "a\nb\nc"
Step 2: "a\nX\nc"     →  diff: same a, del b, add X, same c  ← 产生闪烁
```

**根因**：前缀/后缀算法会将中间的旧行标记为删除、新行标记为新增，造成不必要的视觉闪烁。

### 5.2 explanation 支持的 Markdown 子集

| 语法 | 说明 |
|------|------|
| `**粗体**` | 强调 |
| `` `代码` `` | 行内代码 |
| ` ``` ` 代码块 | 多行代码（可指定语言） |
| `> 引用` | 引用块 |
| `- 列表项` | 无序列表 |
| `\| 表格 \|` | 表格（需完整表头+分隔行） |
| 连续空行 | 段落分隔 |

### 5.3 文件名与 id 一致性

- TOML 文件名：`<algo-id>.toml`（如 `two-sum.toml`）
- `[algorithm].id` 必须与文件名前缀一致（当前无强制性校验，但混乱会导致维护困难）

---

## 6. TOML 语法注意事项

### 6.1 多行字符串

代码和说明使用 TOML `"""` 多行字符串：

```toml
code = """from typing import List

def two_sum(nums: List[int], target: int) -> List[int]:
    \"\"\"找出数组中两数之和等于 target 的两个索引。\"\"\"
    pass"""
```

注意：
- 代码中的 Python 文档字符串 `"""..."""` 需要转义为 `\"\"\"...\"\"\"`
- 也可将中文引号 `""` 替换为 `「」` 避免转义

### 6.2 内联表

`visualizationData` 使用 TOML 内联表语法：

```toml
visualizationData = { mapContents = "{}", arrayState = "[2, 7, 11, 15]", currentIndex = -1 }
```

- 用 `{ }` 包裹，逗号分隔
- **键名不加引号**
- 字符串值用双引号
- 布尔值用 `true` / `false`（全小写）

### 6.3 Windows 编码

Windows 终端运行解析脚本时可能因 GBK 编码报错。已自动处理，如需手动：

```bash
$env:PYTHONIOENCODING = "utf-8"
python scripts/parse_algo.py
```

---

## 7. 完整示例

```toml
[algorithm]
id = "two-sum"
title = "两数之和"
titleEn = "Two Sum"
difficulty = "easy"
tags = ["array", "hash-table"]
testCase = "nums = [2, 7, 11, 15], target = 9"
expectedOutput = "[0, 1]"

# ── Step 0: 题目介绍 ──────────────────────────────────────────
[[algorithm.steps]]
id = 0
title = "理解问题"
titleEn = "Understand the Problem"
code = """# 注释行说明题目"""
explanation = "**问题分析**\n\n说明文字..."
visualizationType = "intro"

# ── Step 1: 函数签名 ──────────────────────────────────────────
[[algorithm.steps]]
id = 1
title = "函数签名"
titleEn = "Function Signature"
code = """# 注释行说明题目

from typing import List

def two_sum(nums: List[int], target: int) -> List[int]:
    \"\"\"文档字符串\"\"\"
    pass"""
explanation = "**第 1 步**\n\n说明..."
visualizationType = "code-only"

# ── Step 2: 初始化哈希表 ──────────────────────────────────────
[[algorithm.steps]]
id = 2
title = "初始化哈希表"
titleEn = "Initialize Hash Table"
code = """# 注释行说明题目

from typing import List

def two_sum(nums: List[int], target: int) -> List[int]:
    \"\"\"文档字符串\"\"\"
    seen = {}  # 新增这行
    pass"""
explanation = "**第 2 步**\n\n说明..."
visualizationType = "map-create"
visualizationData = { mapContents = "{}", arrayState = "[2, 7, 11, 15]", currentIndex = -1 }

# ── ... 更多 steps ─────────────────────────────────────────────

[algorithm.summary]
timeComplexity = "O(n)"
spaceComplexity = "O(n)"
approach = "哈希表（一次遍历）"
keyInsight = "利用字典的 O(1) 查找特性，将双层循环降为单层"
```

---

## 8. 开发命令

```bash
pnpm parse:algos               # 解析所有 TOML → 更新 JSON
pnpm parse:algos:watch         # 监视模式（需 pip install watchdog）
pnpm run build                 # 构建验证
```
