---
name: module-development
description: Use when adding new modules, pages, or widgets to the project registry system
---

# Module Development Workflow

## Core Principle

Manifest-driven module model. Files must exist before registration. Entry paths are resolved eagerly at startup.

## When to Use

- Adding a new module to the project
- Creating a new page under existing module
- Adding a widget to a module or page
- Registering components in `module.meta.js`

## Module Structure

```
src/modules/<module-id>/
  module.meta.js      # Required at root
  pages/              # Route-level screens
    SomePage.jsx
  widgets/            # Mountable panel components
    SomeWidget.jsx
```

## Adding a New Module

1. Create `src/modules/<module-id>/`
2. Create `module.meta.js` with `defineModule()`
3. Create `pages/` subdirectory
4. Create page file first (before registration)
5. Add `definePage()` entry
6. Build with `pnpm run build`

## Adding a New Page

1. Create `src/modules/<module>/pages/<Name>Page.jsx`
2. Export with `export default function`
3. Add `definePage()` in `module.meta.js`
4. `entry: './pages/<Name>Page.jsx'`
5. Ensure `id` and `route` are unique
6. Build and test

## Adding a Widget

1. Create `src/modules/<module>/widgets/<Name>Widget.jsx`
2. Add `defineWidget()` in `module.meta.js`
3. Reference from page with `widgets: ['widget-id']`

## CSS Module Convention

- Component styles go in `<Name>.module.css` beside the component
- Global styles go in `src/app/styles.css`
- Use camelCase class names: `progressFill`, `lineActive`

## Required Metadata

**defineModule:** `id`, `title`, `description`, `order`, `pages`, `widgets`

**definePage:** `id`, `title`, `route`, `entry`, `summary`

**defineWidget:** `id`, `title`, `entry`, `summary`

## Checklist Before Commit

- [ ] File exists before metadata references it
- [ ] `module.meta.js` at module root
- [ ] `entry` starts with `./pages/` or `./widgets/`
- [ ] All `id` values unique
- [ ] All `route` values unique
- [ ] Default export exists
- [ ] `pnpm run build` passes

## Bad Patterns

**Register before file exists:**
```js
entry: './pages/NotYetCreated.jsx' // Will crash at startup
```

**Wrong entry path:**
```js
entry: './NotInPages/Foo.jsx' // Must be ./pages/ or ./widgets/
```

**Duplicate route:**
```js
route: '/reading/story' // Already exists = discovery throws
```
