---
name: rt-componentization
description: Use when adding new components, pages, or modules to the RT React project with its manifest-driven registry system
---

# RT Project Componentization & Module Workflow

## Positioning

RT is a **demo base platform**: each page is an independent fullscreen demo, auto-registered by metadata, listed as a card on the home showcase grid (`/`). Adding a demo = one page file + one `definePage()` entry. No central route table to touch.

## Core Model

Modules are discovered via `module.meta.js` manifests (eager glob). Page/widget code stays lazy — split into chunks, loaded on first visit, preloaded on card/link hover.

```
src/modules/<module-id>/
  module.meta.js      # Registry manifest (eager-loaded, keep it light)
  pages/              # Route-level fullscreen demos
    SomePage.jsx      # ONLY *Page.jsx files are discoverable entries
  widgets/            # Mountable panel components
    SomeWidget.jsx    # ONLY *Widget.jsx files are discoverable entries
  components/ hooks/ utils/ services/ data/   # free-form internals, never registered
```

## Discovery Contract (src/framework/discovery.js)

- Manifest glob: `src/modules/*/module.meta.js` (one level; module folders sit directly under `src/modules/`).
- Entry globs are **convention-narrowed**: `pages/**/*Page.{js,jsx}` and `widgets/**/*Widget.{js,jsx}`. Helper files that don't match the suffix bundle into their importer's chunk instead of becoming standalone lazy chunks.
- **Never name a helper file `*Page.jsx` / `*Widget.jsx`** unless it is a registered entry — matched-but-unregistered files still produce wasted build chunks, and dev mode logs an `[rt-discovery]` orphan warning for them.
- Validation is **aggregated**: startup throws ONE error listing every problem (missing entry, duplicate id, duplicate route, reserved route) — fix all at once.
- Route `/` is **reserved** for the app-level showcase HomePage; module pages must use `/<module>/<feature>`.

## External-First Rule (before writing any new component)

Walk this order; skip a level only with a reason:

1. **npm package first.** Check `package.json`: `@xyflow/react` (node-edge graphs), `marked` (Markdown→HTML), `react-router-dom` (`Link`/`NavLink`/params). Features like "drag/drop nodes", "markdown", "charts", "form validation" → search npm before coding.
2. **Framework primitives next.** `src/framework/components/` + `hooks/`: `FullscreenPage` (page chrome, sets document title from `page.title` — do **not** call `useDocumentTitle` inside a registered page), `WidgetHost` (widget mounting), `NotFoundPage`.
3. **Sibling modules next.** `registry.pages` / `registry.widgets` are the inventory — reuse an existing widget id instead of re-rendering the same UI.
4. **Local module file last.**

## Rendering Model

- Every registered page renders fullscreen at its route via `FullscreenPage` (receives `{ page, registry }` props).
- `showcase: true` (default) → card on the home grid. `internal: true` or `showcase: false` → route works, hidden from home.
- Widgets do not auto-render. A page mounts registered widgets explicitly:

```jsx
import { WidgetHost } from '../../../framework/components/WidgetHost.jsx'
<WidgetHost widgetId="route-map" />
```

## Registry API (src/framework/registry.js)

```js
import { registry, getModulePages, getModuleWidgets, getWidgetById, getShowcasePages } from '../framework/registry.js'
```

- `registry.modules / pages / widgets` — sorted lists; `modulesById / pagesById / widgetsById` — Map lookups.
- `getModulePages(moduleId)` / `getModuleWidgets(moduleId)` — O(1), precomputed per module.
- `getShowcasePages()` — pages shown on the home grid.
- `page.preload()` — warms the lazy chunk (wire to hover/focus).

## Adding a New Demo Page (most common task)

```
1. Create: src/modules/<module>/pages/<Name>Page.jsx  (default export required)
2. Register in module.meta.js:
   definePage({
     id: '<module>-<feature>',        // kebab-case, stable
     title: '...', summary: '...',
     route: '/<module>/<feature>',    // unique, never '/'
     entry: './pages/<Name>Page.jsx',
     tags: ['...']
   })
3. pnpm run build   # aggregated error will list any manifest problems
```

New module = new folder + `module.meta.js` with `defineModule({ id, title, description, order, pages, widgets })`, then same steps.

**File first, register second** — entry paths are resolved at startup; registering a missing file fails the whole registry.

## Naming Convention

- Page files: `*Page.jsx` (registered entries only) · Widget files: `*Widget.jsx`
- Helper/internal files: any other name, any subfolder (`components/`, `hooks/`, `utils/`, ...)
- Routes: `/<module>/<feature>` (param routes allowed: `/algo/visualizer/:slug`)
- Ids: kebab-case, stable, unique project-wide

## CSS in RT

- Global reusable styles: `src/app/styles.css`; component styles: `<Name>.module.css` beside the component (CSS Modules, camelCase class names).
- **Default to the global visual vocabulary first**: `.panel`, `.registry-card`, `.metric-value`, `.tip-card`, `.widget-card`, `.hero-panel`, `.code-panel`, `.tag`, `.toolbar`, `.search-input`, `.empty-card`. Only drop to a `.module.css` for classes that don't exist globally.
- State classes target the direct parent:

```jsx
<span className={`${styles.track}${isActive ? ` ${styles.trackActive}` : ''}`}>
  <span className={styles.fill} />
</span>
```

```css
.trackActive .fill { opacity: 1; }
```

## Pre-Commit Checklist

- [ ] Entry file exists and has a default export
- [ ] Entry named `*Page.jsx` / `*Widget.jsx`, `entry` path starts with `./pages/` or `./widgets/`
- [ ] `id` and `route` unique; route is not `/`
- [ ] No orphan `*Page.jsx`/`*Widget.jsx` files (check dev console for `[rt-discovery]` warnings)
- [ ] `pnpm run build` passes

## Common Mistakes

| Mistake | Why Bad |
|---------|---------|
| Register before file exists | Startup throws (aggregated error lists it) |
| Helper file named `*Page.jsx` but unregistered | Wasted build chunk + dev orphan warning |
| Route `/` on a module page | Reserved for showcase home; discovery rejects it |
| Widget in pages/ folder | Wrong glob — entry won't be found |
| Duplicate id/route | Discovery rejects it |
| Heavy imports in module.meta.js | Manifest is eager-loaded; keep it metadata-only |
| `useDocumentTitle` inside a registered page | `FullscreenPage` already sets it from `page.title` |
| Local CSS class duplicating a global one | `.panel` etc. already exist in `src/app/styles.css` |

## Decision Flow

```
New demo route? → Page (definePage)
Reusable panel mounted by pages? → Widget (defineWidget + WidgetHost)
Only this page uses it? → Internal file (no registration, don't name it *Page.jsx)
New feature boundary? → New module folder + module.meta.js
```
