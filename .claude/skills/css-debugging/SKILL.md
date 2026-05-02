---
name: css-debugging
description: Use when CSS styles are not applying as expected, especially with CSS Modules, nested selectors, or dynamic progress animations
---

# CSS Debugging for React/CSS Modules

## Core Principle

CSS selectors must match actual DOM hierarchy. When styles don't apply, the selector path is broken.

## When to Use

- CSS class added but style not visible
- State-based styles (`.active`, `.revealed`) not toggling
- Progress bar/animation not animating
- CSS Module classes generating unique names but selectors not matching

## DOM Structure First

**Always verify DOM hierarchy before touching CSS.**

```text
.line > button > .sentenceStack > .progressTrack > .progressFill
```

If selector is `.line .progressFill`, it must match this path exactly.

## CSS Module Selector Trap

```css
/* WRONG: .progressFill is not a direct child of .line */
.line.active .progressFill { opacity: 1; }
```

CSS Module generates unique class names but selectors still depend on DOM nesting.

**Solution:** Add state class to the direct parent of the styled element:

```css
.progressTrackActive .progressFill { opacity: 1; }
```

```jsx
<span className={`${styles.progressTrack}${isActive ? ` ${styles.progressTrackActive}` : ''}`}>
```

## Debugging Order

1. **Check DOM** - Verify actual HTML structure in DevTools
2. **Inline style test** - Use inline `style` to confirm React logic works
3. **Selector audit** - Confirm CSS selector path matches DOM
4. **Class application** - Verify state class is actually added to element
5. **Specificity check** - Is another rule overriding?

## Inline Style Debug Pattern

When CSS fails, verify with inline styles:

```jsx
<span style={{
  width: `${progress * 100}%`,
  opacity: isActive ? 1 : 0,
  background: '#21a1f1'
}} />
```

If this works but CSS doesn't → problem in CSS selector.
If this doesn't work → problem in React state/logic.

## Progress Animation Debug

RAF can miss frames. Use setInterval for reliability:

```js
// RAF - may drop frames
const tick = (now) => {
  setProgress((now - startRef.current) / DURATION)
  rafRef.current = requestAnimationFrame(tick)
}

// setInterval - more reliable for progress
const step = 50
let elapsed = 0
intervalRef.current = setInterval(() => {
  elapsed += step
  setProgress(Math.min(elapsed / DURATION, 1))
}, step)
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Selector expects `.parent .child` but child is in different branch | Add state class to direct parent |
| CSS Module compound selector without direct nesting | Use direct parent class with state |
| Duplicate CSS rules (copy-paste) | Search for duplicate selectors |
| CSS transition on wrong property | Ensure transition matches animated property |
| `!important` in base class overriding state | Remove `!important`, use specificity instead |

## Quick Reference

1. Check DOM structure
2. Inline style test
3. Fix selector path
4. Use setInterval for animations
5. Remove `!important` pollution
