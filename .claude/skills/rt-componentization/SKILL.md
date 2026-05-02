---
name: rt-componentization
description: Use when adding new components, pages, or modules to the RT React project with its manifest-driven registry system
---

# RT Project Componentization & Module Workflow

## Core Model

RT uses a **manifest-driven module model** without a central route table. Modules are discovered via `module.meta.js` metadata.

```
src/modules/<module-id>/
  module.meta.js      # Registry entry point
  pages/              # Route-level screens
    SomePage.jsx
  widgets/            # Mountable panel components
    SomeWidget.jsx
```

**Critical rule:** File must exist BEFORE registration. `entry` paths resolve eagerly at startup.

## Component Levels

| Level | Purpose | Registry | File Convention |
|-------|---------|----------|-----------------|
| Module | Feature boundary | `module.meta.js` | Folder under `src/modules/` |
| Page | Route screen | `definePage()` in `module.meta.js` | `pages/*Page.jsx` |
| Widget | Mountable panel | `defineWidget()` in `module.meta.js` | `widgets/*Widget.jsx` |
| Internal | Implementation detail | None | Inside page file |

## When to Use Each Level

- **New route needed?** → Page
- **Mounted inside a page?** → Widget
- **Used only within this page?** → Internal component (no registration)

## Adding a New Module

```
1. Create: src/modules/<module-id>/
2. Create: module.meta.js with defineModule()
3. Create: pages/ directory
4. Create: First page file
5. Register: definePage() entry
6. Build: pnpm run build
```

## Adding a New Page

```
1. Create: src/modules/<module>/pages/<Name>Page.jsx
2. Export: export default function <Name>Page()
3. Register: definePage() in module.meta.js
   - entry: './pages/<Name>Page.jsx'
   - route: '/<module>/<name>' (unique)
   - id: unique identifier
4. Build and test
```

## Naming Convention

```
Module folder: reading
Module id: reading
Page id: story-reader
Route: /reading/story
File: SentenceReaderPage.jsx
Widget id: route-map
Widget file: RouteMapWidget.jsx
```

- Page files: `*Page.jsx`
- Widget files: `*Widget.jsx`
- Routes: `/<module>/<feature>`
- Ids: kebab-case, stable (not dynamic)

## File Creation Order (Critical)

1. Create runtime file FIRST
2. Then register metadata
3. Never register what doesn't exist

This order matters because `src/framework/discovery.js` resolves `entry` paths eagerly.

## CSS in RT

- **Global reusable styles:** `src/app/styles.css`
- **Component-specific styles:** `<Name>.module.css` beside component
- **RT uses CSS Modules** for scoped styling
- **Avoid** global CSS for component-specific styles

## CSS Module Pattern for RT

```jsx
import styles from './MyComponent.module.css'

// State classes need direct parent targeting
<span className={`${styles.track}${isActive ? ` ${styles.trackActive}` : ''}`}>
  <span className={styles.fill} />
</span>
```

```css
/* Correct: state class on direct parent */
.trackActive .fill { opacity: 1; }
```

## Required Metadata Fields

**defineModule:**
- `id`, `title`, `description`, `order`, `pages[]`, `widgets[]`

**definePage:**
- `id`, `title`, `route`, `entry`, `summary`
- Optional: `order`, `tags`, `widgets[]`

**defineWidget:**
- `id`, `title`, `entry`, `summary`
- Optional: `order`, `tags`

## Pre-Commit Checklist

- [ ] File exists before metadata references it
- [ ] `module.meta.js` at module root
- [ ] `entry` starts with `./pages/` or `./widgets/`
- [ ] All `id` values unique across project
- [ ] All `route` values unique
- [ ] Default export exists
- [ ] CSS Module naming uses camelCase
- [ ] `pnpm run build` passes

## Common Mistakes

| Mistake | Why Bad |
|---------|---------|
| Register before file exists | Startup throws - discovery resolves eagerly |
| Widget in pages/ folder | Breaks page/widget separation |
| Duplicate route | Discovery throws |
| Dynamic ids | Breaks widget references |
| Wrong entry path | File not found at startup |

## Decision Flow

```
Need new route? → Page under existing or new module
Mounted inside page? → Widget
Only this page uses? → Internal component (no registration)
New feature boundary? → New module
```
