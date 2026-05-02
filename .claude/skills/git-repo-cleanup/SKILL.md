---
name: git-repo-cleanup
description: |
  Use when git status shows nested repos as "modified", gitlinks are tracked,
  or git history contains cloned repositories that should be isolated.
  Triggers: "清理git", "处理嵌套仓库", "git隔离", "保持干净", "不在历史显示".
---

# git-repo-cleanup 工作流程

## 问题背景

`.claude/repo/` 等目录包含通过 git clone 下载的嵌套仓库。这些仓库会被 git 检测为：
- 修改 (modified content)
- 嵌套 gitlink (作为子模块被跟踪)

导致 `git status` 不干净，`git add .` 会污染暂存区。

## 工作流程

### 1. 检查当前状态

```bash
# 查看哪些嵌套仓库被跟踪
git ls-files --stage .claude/repo/

# 查看 git status
git status
```

### 2. 添加到 .gitignore

在项目 `.gitignore` 中添加规则：

```bash
# Cloned repositories (nested git repos)
.claude/repo/
```

### 3. 从 git 跟踪中移除

**如果是被跟踪的 gitlink (子模块)**：
```bash
git rm --cached -r .claude/repo/
```

**如果只是嵌套仓库（未被跟踪但有 modified content）**：
```bash
# 只需确保 .gitignore 生效
# 无需其他操作
```

### 4. 验证结果

```bash
# 确认暂存区干净
git status

# 确认 .gitignore 生效
echo ".claude/repo/" >> .gitignore

# 提交更改
git add .gitignore
git commit -m "chore: ignore .claude/repo/ for cloned repos isolation"
```

## 验证标准

完成后应满足：
- `git status` 显示 `nothing to commit, working tree clean`
- `git add .` 不会暂存 `.claude/repo/` 下的任何文件

## 完全清除历史记录

如果需要在 **Git 历史中** 完全移除某个嵌套仓库（不只是从跟踪中移除），使用 `git filter-branch`：

```bash
# 1. 先暂存当前工作区更改（filter-branch 要求工作区干净）
git stash

# 2. 执行历史重写，移除指定路径
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch -r .claude/repo/<目标仓库>" \
  --prune-empty --tag-name-filter cat -- --all

# 3. 恢复工作区
git stash pop
```

**注意**：
- 这会重写 Git 历史，请确认没有其他协作者依赖这些提交
- 需要 `git push --force` 才能更新远程
- `--ignore-unmatch` 防止路径不存在时出错

## 常见问题

| 问题 | 解决 |
|------|------|
| 嵌套仓库显示 "modified content" | 确保目录在 .gitignore 中 |
| gitlink 被跟踪 | `git rm --cached -r <path>` |
| 暂存区有删除记录 | `git reset HEAD <path>` |
| 无法提交 .gitignore | `git add .gitignore` 显式添加 |
| 历史中仍显示嵌套仓库 | 使用 git filter-branch 完全清除历史 |
| filter-branch 失败 | 先 `git stash` 暂存更改 |
