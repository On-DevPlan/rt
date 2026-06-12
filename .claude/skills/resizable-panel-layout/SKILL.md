---
name: resizable-panel-layout
description: 当需要为 React 页面实现可拖拽调整大小的模块化面板布局时触发。包括左右分栏、上下分栏、拖拽手势修复、flex 填充等常见问题。
---

# Resizable Panel Layout — 可拖拽调整大小的模块化面板布局

## 核心实现

### 布局结构

```
┌─────────────────┬─┬─────────────────┐
│   代码区 (flex:1) │ │                 │
├───────────────── ║ ├─────────────────┤
│ 可视化区 (height) ║ │   右侧说明面板   │
│  ↑ 水平分隔条可拖拽│ │   (flex:1)     │
└─────────────────┴─┴─────────────────┘
          ↑ 垂直分隔条可拖拽
```

### CSS 关键规则

| 面板 | 必需属性 | 说明 |
|------|---------|------|
| 左/上面板 | `width: N%`（JS 控制） | 不要写死 flex 数字 |
| 右/下面板 | `flex: 1` | 自动填满剩余空间（易遗漏！） |
| 所有面板 | `min-width` / `min-height` | 防止缩得过小 |
| 分隔条 | `flex-shrink: 0` | 防止被压缩 |

### 分隔条 CSS 模板

```css
/* 垂直分隔条（左右调整） */
.splitV {
  width: 5px;
  cursor: col-resize;
  flex-shrink: 0;
  background: var(--algo-border);
  transition: background 0.15s;
}
.splitV::after {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 3px; height: 32px;
  background: var(--algo-textDim);
  border-radius: 2px;
  opacity: 0.4;
}
.splitV:hover { background: var(--algo-cyan); }

/* 水平分隔条（上下调整） */
.splitH {
  height: 5px;
  cursor: row-resize;
  flex-shrink: 0;
  background: var(--algo-border);
  transition: background 0.15s;
}
.splitH::after {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  height: 3px; width: 32px;
  background: var(--algo-textDim);
  border-radius: 2px;
  opacity: 0.4;
}
.splitH:hover { background: var(--algo-cyan); }
```

### React 拖拽实现模板

```jsx
// 状态
const [leftWidthPct, setLeftWidthPct] = useState(62)
const [vizHeightPx, setVizHeightPx] = useState(220)
const pageRef = useRef(null)

// 垂直分隔条拖拽（左右调整宽度）
const startDragV = useCallback((e) => {
  e.preventDefault()
  const startX = e.clientX
  const startPct = leftWidthPct
  const containerW = pageRef.current.getBoundingClientRect().width
  const onMove = (me) => {
    const dx = me.clientX - startX
    const newPct = Math.min(80, Math.max(20, startPct + (dx / containerW) * 100))
    setLeftWidthPct(newPct)
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}, [leftWidthPct])

// 水平分隔条拖拽（上下调整高度）
// 关键：分隔条在可视区上方，向下拖 = 可视区变小 → dy 正时 height 减小
const startDragH = useCallback((e) => {
  e.preventDefault()
  const startY = e.clientY
  const startPx = vizHeightPx
  const onMove = (me) => {
    const dy = me.clientY - startY
    // 向下拖 dy>0 → 可视区减小
    const newPx = Math.min(leftH - 120, Math.max(100, startPx - dy))
    setVizHeightPx(newPx)
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}, [vizHeightPx])
```

### JSX 模板

```jsx
<div className={styles.page} ref={pageRef}>
  <div className={styles.leftPanel} style={{ width: `${leftWidthPct}%` }}>
    <div className={styles.codeSection}>代码区</div>
    <div className={`${styles.splitH} ${isDraggingH ? styles.dragging : ''}`}
         onMouseDown={startDragH} />
    <div className={styles.vizSection} style={{ height: vizHeightPx }}>可视化区</div>
  </div>

  <div className={`${styles.splitV} ${isDraggingV ? styles.dragging : ''}`}
       onMouseDown={startDragV} />

  <div className={styles.rightPanel}>右侧说明面板</div>
</div>
```

## 错误案例

| 错误操作 | 实际后果 | 正确做法 |
|---------|---------|---------|
| 右侧/下方面板缺 `flex: 1` | 面板只占内容宽度，剩余空白 | 必须加 `flex: 1` |
| 水平分隔条拖动方向符号写反 | 向下拖分隔条，可视区反而变大 | `startPx - dy`（分隔条在可视区上方） |
| 分隔条未设 `flex-shrink: 0` | 面板缩小时分隔条也被压缩 | 加上 `flex-shrink: 0` |
| 拖动时没设 `user-select: none` | 拖动过程中文字被选中，体验差 | 在 `.mainContent` 加 `user-select: none` |
| `onMouseDown` 没用 `e.preventDefault()` | 拖动时浏览器触发文字选择/拖放 | 必须 `e.preventDefault()` |
| 左侧宽度用 `flex: 3` 写死 | 无法实现 JS 精确控制宽度 | 用 `width: ${leftWidthPct}%` |
| 拖动时不移除全局事件监听 | 多次拖动后事件堆积，拖动飘移 | `mouseup` 时必须 `removeEventListener` |
| 同时监听 `mousemove` 和 `mouseup` 不做清理 | 页面跳转后监听器仍在，内存泄漏 | 用 `onUp` 函数统一清理 |

## 成功标准检查清单

- [ ] 左侧面板宽度由 JS `leftWidthPct` 控制，有 `width: ${leftWidthPct}%`
- [ ] 右侧面板有 `flex: 1` 自动填满剩余空间
- [ ] 可视化区高度由 JS `vizHeightPx` 控制，有 `style={{ height: vizHeightPx }}`
- [ ] 分隔条有 `onMouseDown={startDrag}` 且调用了 `e.preventDefault()`
- [ ] `mouseup` 时正确移除 `mousemove` 和 `mouseup` 监听
- [ ] 水平分隔条方向公式为 `startPx - dy`（向下拖=减小）
- [ ] 所有面板有 `min-width` / `min-height` 限制
- [ ] `build` 通过无报错
