---
name: algo-toml-workflow
description: 当需要为算法可视化扩展新 TOML 文件时触发，包括从任务规划到最终验证的完整流程。
---

# 算法 TOML 可视化扩展流程

## 适用场景

需要为 Algorithm Lab 添加新的算法题目时，遵循本流程。

## 完整流程

### Step 1: 创建参考文件

从 `scripts/all-algorithms.json` 确认题目是否在清单中。

### Step 2: 编写 TOML 文件

在 `public/algos/` 目录下创建 `<slug>.toml`，参考 spec：

**必填字段：**
```toml
[algorithm]
id = "slug-name"           # 英文 slug，与文件名一致
title = "中文标题"
titleEn = "English Title"
difficulty = "easy|medium|hard"
tags = ["tag1", "tag2"]
testCase = "参数"
expectedOutput = "结果"

[[algorithm.steps]]
id = 0
title = "步骤标题"
titleEn = "Step Title"
code = """代码内容"""   # 多行字符串，Python 语法
explanation = "**Markdown** 解释内容"
visualizationType = "intro|code-only|map-create|array-iteration|map-add|map-found|result"
```

**TOML 规范（高频坑点）：**

| 规则 | 错误写法 | 正确写法 |
|------|---------|---------|
| Python `"""` 必须转义 | `"""` | `\"\"\"` |
| TOML 布尔值小写 | `yes` / `no` | `true` / `false` |
| inline table key 不加引号 | `{ "key" = 1 }` | `{ key = 1 }` |
| explanation 使用 GFM Markdown | plain text | `**bold**, `code`, 表格, 列表` |
| `mapContents` 格式 | `{2: 0}` | `"{2 → 0}"`（U+2192） |

**步骤规范：**
- 步骤数量：4-6 步
- 代码连续性：每步的 `code` 只能新增行，不能修改已有行
- 第一步 `visualizationType` 用 `intro`
- 最后一步用 `result`，且需含 `visualizationData`
- 中间步骤用 `code-only` 或对应可视化类型

### Step 3: 解析验证

```bash
python3 scripts/parse_algo.py
```

- 成功输出：`+ algorithm\data\<slug>.json`
- 错误输出：`x Error: Illegal character '\n' (at line XX, column XX)`
- 常见错误：explanation 中的代码块未正确转义多行字符串

### Step 4: 审计检查

```bash
node scripts/_audit.cjs
```

检查项：
1. step 数量 4-6
2. 代码连续性（每步只新增行）
3. visualizationType 枚举值合法
4. inline table key 未加引号

### Step 5: 更新 index.json

`parse_algo.py` 会自动追加到 `src/modules/algorithm/data/index.json`。

### Step 6: 更新分组索引（如需）

若新题目属于新分类或现有分类，编辑 `src/modules/algorithm/data/grouped-index.json`。

## 核心文件位置

| 文件 | 作用 |
|------|------|
| `public/algos/*.toml` | 源数据 |
| `src/modules/algorithm/data/*.json` | 解析产物 |
| `src/modules/algorithm/data/index.json` | 算法索引 |
| `src/modules/algorithm/data/grouped-index.json` | 分组索引 |
| `scripts/parse_algo.py` | TOML → JSON 解析 |
| `scripts/_audit.cjs` | 规范审计 |
| `docs/algo-toml-spec.md` | TOML 规范文档 |

## 错误案例

| 错误操作 | 实际后果 | 正确做法 |
|---------|---------|---------|
| explanation 中直接写多行代码块 | TOML 解析失败 `Illegal character '\n'` | 用 `\n` 转义或改用单行描述 |
| Python `"""` 未转义 | TOML 多行字符串提前关闭 | 全部写成 `\"\"\"` |
| visualizationType 拼写错误 | 可视化组件不渲染 | 对照 enum 值：`intro`, `code-only`, `map-create`, `array-iteration`, `map-add`, `map-found`, `result` |
| step 的 code 修改了前序行 | 代码连续性审计失败 | 每步只能追加新行 |
| `testCase` 含有特殊字符 | TOML 解析歧义 | 用双引号包裹 |

## 坑点警示

1. **TOML 多行字符串中的代码**：explanation 字段内嵌代码块时，确保缩进正确且不破坏 TOML 解析
2. **字符编码**：`mapContents` 箭头必须用 U+2192 (→)，不是 `->`
3. **parse_algo.py vs audit**：解析器报错时 audit 可能仍然通过，以 parse_algo.py 为准
4. **批量生成**：使用并行 agent 时，注意 429 限流错误，文件仍可能成功生成
