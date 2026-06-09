# Algorithm Lab — TOML Spec v2（AI Agent 优化版）

> 本规范专为 AI Agent 编写 TOML 而优化。快速入口见 §0 模板，关键约束见 §5。

---

## §0 快速模板（AI 从这里开始）

```toml
[algorithm]
id = "your-algo-id"              # 唯一，用作文件名和数据 key，全小写连字符
title = "中文标题"
titleEn = "English Title"
difficulty = "easy"              # easy | medium | hard
tags = ["array", "hash-table"]  # 分类标签，至少一个

# ── 第 1 步：题目介绍 ──────────────────────────────────
[[algorithm.steps]]
id = 0
title = "理解问题"
titleEn = "Understand the Problem"
code = """# 第一行是注释，说明题目
# 后续行用注释描述"""
explanation = "**问题分析**\n\n说明文字..."
visualizationType = "intro"

# ── 第 2 步：函数签名 ──────────────────────────────────
[[algorithm.steps]]
id = 1
title = "函数签名"
titleEn = "Function Signature"
code = """# 第一行注释不变

from typing import List

def your_func(params) -> ReturnType:
    \"\"\"文档字符串\"\"\"
    pass"""
explanation = "**第 1 步**\n\n说明..."
visualizationType = "code-only"

# ── 后续步骤：逐步添加代码行 ────────────────────────────
[[algorithm.steps]]
id = 2
title = "..."
titleEn = "..."
code = """# 第一行注释不变
# ...（包含上一步所有代码 + 新增行）

from typing import List

def your_func(params) -> ReturnType:
    \"\"\"文档字符串\"\"\"
    seen = {}  # ← 新增这行
    pass"""
explanation = "**第 2 步**\n\n说明..."
visualizationType = "map-create"
visualizationData = { mapContents = "{}", arrayState = "[1, 2, 3]", currentIndex = -1 }

# ── 更多 steps ... ──────────────────────────────────────

# ── 最后一步：完整代码, visualizationType = "result" ────
[[algorithm.steps]]
id = 5
title = "完成"
titleEn = "Complete"
code = """# ... 完整最终代码 ..."""
explanation = "**最终结果**\n\n说明..."
visualizationType = "result"
visualizationData = { mapContents = "{1 → 0}", arrayState = "[1, 2, 3]", result = "[0, 1]", highlightedIndices = [0, 1] }

[algorithm.summary]
timeComplexity = "O(n)"
spaceComplexity = "O(n)"
approach = "方法简述"
keyInsight = "一句话核心启发"
```

---

## §1 概述

数据链路：`TOML → Python/Pygments → JSON → React`，TOML 是唯一数据源。

```
public/algos/<algo-id>.toml    ← AI 在这里工作
       │
       ▼ (pnpm parse:algos)
scripts/parse_algo.py          ← 自动解析、着色、校验
       │
       ▼
src/modules/algorithm/data/    ← 生成的 JSON，前端自动发现
```

**添加新算法的步骤**（无需改前端代码）：

1. 在 `public/algos/` 下创建 `<algo-id>.toml`
2. 运行 `pnpm parse:algos`
3. 运行 `pnpm run build`

---

## §2 `[algorithm]` 算法元信息

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | `string` | **是** | — | 唯一标识，全小写连字符，如 `"two-sum"` |
| `title` | `string` | **是** | — | 中文标题 |
| `titleEn` | `string` | 否 | `""` | 英文标题 |
| `difficulty` | `string` | 否 | `"medium"` | 枚举：`"easy"` / `"medium"` / `"hard"` |
| `tags` | `string[]` | 否 | `[]` | 分类标签，如 `["array", "hash-table"]` |
| `testCase` | `string` | 否 | `""` | 示例测试用例，纯展示 |
| `expectedOutput` | `string` | 否 | `""` | 预期输出，纯展示 |

---

## §3 `[[algorithm.steps]]` 步骤定义

### 3.1 通用字段

| 字段 | 类型 | 必需 | 默认值 | 约束 |
|------|------|------|--------|------|
| `id` | `int` | 否 | 从 0 递增 | 建议每步 +1 |
| `title` | `string` | **是** | — | 中文步骤名，4-8 字 |
| `titleEn` | `string` | 否 | `""` | 英文步骤名 |
| `code` | `string` | **是** | — | **MUST** 包含上一步所有代码行 + 新增行 |
| `explanation` | `string` | **是** | — | GFM Markdown（[marked](https://marked.js.org/) 解析），支持表格/代码块/引用/列表/粗体/行内代码等完整规范 |
| `visualizationType` | `string` | 否 | `"code-only"` | 见 §3.2 |
| `visualizationData` | `table` | 否 | `{}` | 字段由 visualizationType 决定，见 §3.3 |

### 3.2 `visualizationType` 枚举

| 类型 | 场景 | 布局 | 需要 visualizationData？ |
|------|------|------|--------------------------|
| `"intro"` | 题目介绍 | 居中说明文字 | 不需要 |
| `"code-only"` | 仅展示代码 | 小图标提示 | 不需要 |
| `"map-create"` | 初始化哈希表 | 数组 + 空 Map | 需要 |
| `"array-iteration"` | 遍历数组，查找补数 | 数组 + Map + 补数徽章 | 需要 |
| `"map-add"` | 元素存入哈希表 | 数组 + Map + 插入操作提示 | 需要 |
| `"map-found"` | 找到匹配结果 | 数组(高亮) + Map + 成功提示 | 需要 |
| `"result"` | 最终结果 | 数组(高亮) + Map + 结果徽章 | 需要 |

### 3.3 `visualizationData` 字段速查

#### `"map-create"` — 初始化
```toml
visualizationData = { mapContents = "{}", arrayState = "[2, 7, 11, 15]", currentIndex = -1 }
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `mapContents` | `string` | 是 | 格式 `"{key → value}"`，空表 `"{}"` |
| `arrayState` | `string` | 是 | 数组字符串，如 `"[2, 7, 11, 15]"` |
| `currentIndex` | `int` | 否 | 高亮索引，`-1` 表示无 |

#### `"array-iteration"` — 遍历查找
```toml
visualizationData = { mapContents = "{2 → 0}", arrayState = "[2, 7, 11, 15]", currentIndex = 1, complement = 7, found = false }
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `mapContents` | `string` | 是 | 当前 Map 状态 |
| `arrayState` | `string` | 是 | 数组字符串 |
| `currentIndex` | `int` | 是 | 当前遍历索引 |
| `currentValue` | `int` | 否 | 当前元素值 |
| `complement` | `int` | 否 | 计算出的补数 |
| `found` | `bool` | 否 | **TOML 布尔，小写**：`true` / `false` |

#### `"map-add"` — 存入 Map
```toml
visualizationData = { mapContents = "{2 → 0}", arrayState = "[2, 7, 11, 15]", currentIndex = 0, mapKey = 2, mapValue = 0 }
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `mapContents` | `string` | 是 | 插入后的 Map 状态 |
| `arrayState` | `string` | 是 | 数组字符串 |
| `currentIndex` | `int` | 是 | 当前索引 |
| `mapKey` | `int` | 是 | 正在插入的键 |
| `mapValue` | `int` | 是 | 正在插入的值 |

#### `"map-found"` — 命中
```toml
visualizationData = { mapContents = "{2 → 0}", arrayState = "[2, 7, 11, 15]", currentIndex = 1, complement = 2, foundIndex = 0 }
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `mapContents` | `string` | 是 | 当前 Map 状态 |
| `arrayState` | `string` | 是 | 数组字符串 |
| `currentIndex` | `int` | 是 | 当前索引 |
| `complement` | `int` | 是 | 补数（即 map 中已存在的值） |
| `foundIndex` | `int` | 是 | Map 中匹配的索引 |
| `currentValue` | `int` | 否 | 当前元素值 |
| `result` | `string` | 否 | 结果字符串，如 `"[0, 1]"` |

#### `"result"` — 完成
```toml
visualizationData = { mapContents = "{2 → 0}", arrayState = "[2, 7, 11, 15]", result = "[0, 1]", highlightedIndices = [0, 1] }
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `mapContents` | `string` | 是 | 最终 Map 状态 |
| `arrayState` | `string` | 是 | 最终数组字符串 |
| `result` | `string` | 是 | 结果字符串 |
| `highlightedIndices` | `int[]` | 否 | 高亮的索引数组 |

---

## §4 `[algorithm.summary]` 复杂度总结

```toml
[algorithm.summary]
timeComplexity = "O(n)"
spaceComplexity = "O(n)"
approach = "哈希表（一次遍历）"
keyInsight = "一句话点明核心思想"
```

所有字段均为可选 string。

---

## §5 关键约束（AI 最容易出错的地方）

### ⚠️ 规则 1：代码连续性 — 这是最重要的约束

**相邻步骤的 `code` 字段必须保持公共前缀和后缀一致。**

每步只能**新增**代码行，不能删除或修改已有的行。AI 在"重构"或"简化"代码时容易违反此规则。

```
✅ 正确（只增不减）：
Step 1: "a\na = 1\npass"
Step 2: "a\na = 1\nb = 2\npass"   ← 只加了 "b = 2"
Step 3: "a\na = 1\nb = 2\nc = 3\npass"  ← 只加了 "c = 3"

❌ 错误（AI 常见错误）：
Step 1: "a\na = 1\npass"
Step 2: "a\na = 2\npass"           ← 把 "a = 1" 改成 "a = 2" → diff 视为删除+新增
```

**为什么？** 前端 diff 引擎使用前缀/后缀匹配算法，不支持行内修改检测。修改中间行会产生大量 delete+add，造成视觉闪烁。

### ⚠️ 规则 2：Python `"""` 文档字符串逃逸

在 TOML `"""` 多行字符串中，Python 的 `"""..."""` 文档字符串必须转义为 `\"\"\"...\"\"\"`：

```toml
code = """def foo():
    \"\"\"这是文档字符串\"\"\"
    pass"""
```

另一种方式：用 `「」` 代替 `""` 避免转义。

### ⚠️ 规则 3：TOML 布尔值全小写

```toml
visualizationData = { found = true }    # ✅ 正确
visualizationData = { found = True }    # ❌ 错误！True 不是 TOML 布尔
visualizationData = { found = "true" }  # ❌ 错误！这是字符串不是布尔
```

### ⚠️ 规则 4：字段名不加引号（内联表语法）

```toml
visualizationData = { mapContents = "{}", currentIndex = -1 }  # ✅ 正确
visualizationData = { "mapContents" = "{}" }                   # ❌ 不需要引号
```

### ⚠️ 规则 5：步骤数

建议 4-6 步。太少的步骤缺乏渐进感，太多步骤说明冗余。

典型的步骤结构：
| 步骤 | visualizationType | 代码状态 |
|------|-------------------|----------|
| 0 | `intro` | 只有注释（无实际代码） |
| 1 | `code-only` | 函数签名 + pass |
| 2 | 按需选择 | + 变量初始化 |
| 3 | 按需选择 | + 核心逻辑 |
| 4 | `result` | 完整代码 |

### ⚠️ 规则 6：`explanation` 使用完整 GFM Markdown

`explanation` 字段使用 [marked](https://marked.js.org/) 解析，支持 **完整 GitHub Flavored Markdown**：

| 语法 | 说明 | 示例 |
|------|------|------|
| `**粗体**` | 强调 | `**重要提示**` |
| `` `代码` `` | 行内代码 | `` 使用 `dict.get()` 方法 `` |
| ` ``` ` 代码块 | 多行代码（可指定语言） | ` ```python ` + 代码 + ` ``` ` |
| `> 引用` | 引用块 | `> 注意边界条件` |
| `- 列表` | 无序列表 | `- 第一步\n- 第二步` |
| `1. 列表` | 有序列表 | `1. 初始化\n2. 遍历` |
| `\| 表格 \|` | 表格 | 标准 GFM 表格语法 |
| 空行分段 | 段落分隔 | 连续两个换行 |
| `` ~~删除线~~ `` | 删除线 | `~~已废弃~~` |
| `` `[链接](url)` `` | 链接 | `[LeetCode](https://leetcode.com)` |
| `` `![图片](url)` `` | 图片 | 少用 |

> 不再有 Markdown 子集限制。所有标准 GFM 语法均可使用。
> 建议保持说明简洁，适度使用表格和代码块提高可读性。

### ⚠️ 规则 7：TOML 字符串中的引号

TOML 的 `"""` 字符串中，如果内容包含连续 3-4 个 `"`，需要转义：

```toml
explanation = """他说「你好」"""  # ✅ 可以用「」代替中文引号
explanation = """他说 \"你好\""""  # ✅ 或者转义
```

---

## §6 AI Agent 自我检查清单

生成完 TOML 文件后，逐项检查：

- [ ] `[algorithm].id` 与文件名 `<algo-id>.toml` 一致
- [ ] 所有相邻步骤的 `code` 字段：**后一步包含前一步的全部代码行**，只增不改
- [ ] Python 文档字符串 `"""..."""` 已转义为 `\"\"\"...\"\"\"`
- [ ] TOML 布尔值使用 `true`/`false`（全小写，不是 Python 的 True/False）
- [ ] `visualizationData` 字段名**不加引号**：`{ key = value }` 不是 `{ "key" = value }`
- [ ] `visualizationType` 在枚举范围内（`intro`, `code-only`, `map-create`, `array-iteration`, `map-add`, `map-found`, `result`）
- [ ] 每个非纯代码步骤（`map-create`/`array-iteration`/等）的 `visualizationData` 字段齐全
- [ ] `mapContents` 格式正确：`"{2 → 0}"`（箭头两侧有空格）或 `"{}"`
- [ ] `arrayState` 格式正确：`"[2, 7, 11, 15]"`（逗号+空格分隔）
- [ ] `explanation` 中无失控的 TOML 字符串（检查引号是否匹配）
- [ ] 步骤数在 4-6 之间，循序渐进
- [ ] `pnpm parse:algos` 解析无报错
- [ ] `pnpm run build` 构建无报错

---

## §7 常见 AI 错误记录

| 错误操作 | 后果 | 正确做法 |
|---------|------|---------|
| 相邻步骤的 code 不一致（修改了中间行） | diff 产生大量 delete+add，动画闪烁 | 每步只增不改，保持公共前缀/后缀 |
| Python `"""` 文档字符串未转义 | TOML 解析器提前关闭字符串 | 用 `\"\"\"` 代替 `"""` |
| 布尔值写成 `True`/`False` | TOML 解析失败 | 用 `true`/`false` |
| `visualizationData` 字段名加引号 | 不是标准 TOML 内联表语法 | 字段名不加引号 |
| 编写超长 explanation（超过 200 字） | 步骤说明过长，阅读体验差 | 保持简洁，用表格/列表分段 |
| 步骤数过多（> 8 步） | 用户失去耐心 | 控制在 4-6 步 |
| `explanation` 过于冗长（整段无分段） | 阅读困难，用户失去耐心 | 用空行分段，适当使用表格/列表/代码块组织内容 |
| `mapContents` 中箭头格式错误（如用 `->` 而不是 `→`） | 前端解析错误 | 用 `→`（`→`），如 `"{2 → 0}"` |

---

## §8 开发命令

```bash
pnpm parse:algos               # 解析所有 TOML → JSON
pnpm run build                 # 构建验证
```

