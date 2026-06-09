---
name: module-development
description: Use when adding new modules, pages, or widgets to the project registry system
---

# Module Development Workflow

## Core Principle

Manifest-driven module model. Files must exist before registration. Entry paths are resolved eagerly at startup.

## External-First Rule (read this before writing anything)

Before you create a new component, page, or widget, walk this decision order. **Skip a level only with a written reason.**

1. **External npm package first.** Check `package.json`. Known candidates:
   - `@xyflow/react` — node-edge graph rendering (used by `workflow/`).
   - `marked` — Markdown → HTML for the `algorithm/` TOML `explanation` field.
   - `react-router-dom` — `<Link>`, `NavLink`, `useNavigate`, route params.
   - If a feature looks like "drag/drop nodes", "markdown", "rich text", "icons",
     "charts", "virtualised list", "form validation" — search npm before coding.
2. **Framework primitives next.** `src/framework/components/` and `src/framework/hooks/`
   are the shared kernel. New pages and widgets **must** use these instead of
   reinventing:
   - `<FullscreenPage>` / `<PageFrame>` — page chrome, `useDocumentTitle` is wired in
     automatically. Do **not** call `useDocumentTitle` from a page — the framework
     already sets it from `page.title`.
   - `<WidgetHost>` — sidebar widget mounting. Do not lazy-load widgets manually.
   - `useDocumentTitle` — only use it from custom routes (e.g. `HomePage`),
     **never** from a registered page, because the framework overrides it.
   - Global CSS classes (`.panel`, `.registry-card`, `.metric-value`, `.tip-card`,
     `.widget-card`, `.hero-panel`, `.code-panel`, `.tag`, `.toolbar`,
     `.search-input`, `.empty-card`) are the visual vocabulary. New components
     reach for these class names before inventing a new CSS module.
3. **Sibling module widgets/pages next.** `registry.widgets` and `registry.pages`
   are the inventory of what is already mounted. If a sibling already exposes a
   reusable widget (stats, route map, contract card, etc.), reference it via
   `widgets: ['widget-id']` in `definePage` instead of re-rendering the same UI.
4. **Local module file last.** Only when the three levels above do not cover the
   need should you create a new `.jsx` under your module.

The rule has two failure modes it is trying to prevent:

- **Dead framework code.** A primitive exists but no module uses it
  (e.g. `PageFrame` is shipped in `framework/components/` but never wired into
  `App.jsx` — if you need a page with widgets today, fix the primitive or
  use `<FullscreenPage>` deliberately, do not duplicate it locally).
- **Per-page title setting.** Pages that import `useDocumentTitle` are
  duplicating what `<FullscreenPage>` does. Strip those calls.

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

1. Walk the External-First Rule above. If a sibling module already covers the
   intent, extend that module instead of forking a new one.
2. Create `src/modules/<module-id>/`
3. Create `module.meta.js` with `defineModule()`
4. Create `pages/` subdirectory
5. Create page file first (before registration)
6. Add `definePage()` entry
7. Build with `pnpm run build`

## Adding a New Page

1. Walk the External-First Rule. In particular:
   - Do you actually need a new page, or can the existing
     `RegistryExplorerPage` / `LandingPage` host a tab?
   - Does the new page render widgets? If yes, list them in
     `widgets: [...]` and let `<FullscreenPage>` mount them — do not
     import widgets directly.
2. Create `src/modules/<module>/pages/<Name>Page.jsx`
3. Export with `export default function`
4. Add `definePage()` in `module.meta.js`
5. `entry: './pages/<Name>Page.jsx'`
6. Ensure `id` and `route` are unique
7. Build and test

## Adding a Widget

1. Walk the External-First Rule. Look at existing widgets in
   `src/modules/*/widgets/` — many already cover stats, route maps, contracts.
2. Create `src/modules/<module>/widgets/<Name>Widget.jsx`
3. Add `defineWidget()` in `module.meta.js`
4. Reference from page with `widgets: ['widget-id']`

## CSS Module Convention

- Component styles go in `<Name>.module.css` beside the component
- Global styles go in `src/app/styles.css`
- **Default to global classes first.** If `.panel`, `.registry-card`,
  `.metric-value`, `.tip-card`, `.widget-card`, `.code-panel` cover the visual
  intent, use them. Only drop to a `.module.css` when you need a class that
  does not exist globally.
- Use camelCase class names: `progressFill`, `lineActive`

## Required Metadata

**defineModule:** `id`, `title`, `description`, `order`, `pages`, `widgets`

**definePage:** `id`, `title`, `route`, `entry`, `summary`

**defineWidget:** `id`, `title`, `entry`, `summary`

## Checklist Before Commit

- [ ] External-First Rule walked; npm / framework / sibling modules checked
- [ ] File exists before metadata references it
- [ ] `module.meta.js` at module root
- [ ] `entry` starts with `./pages/` or `./widgets/`
- [ ] All `id` values unique
- [ ] All `route` values unique
- [ ] Default export exists
- [ ] No redundant `useDocumentTitle` call inside registered pages
- [ ] No manual widget import — widgets are listed in `definePage.widgets`
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

**Reinventing the framework title hook:**
```jsx
import { useDocumentTitle } from '../../../framework/hooks/useDocumentTitle.js'
useDocumentTitle('报名管理') // <FullscreenPage> already does this
```

**Importing widgets directly instead of via manifest:**
```jsx
import { SomeWidget } from '../widgets/SomeWidget.jsx'
<SomeWidget /> // Should be widgets: ['some-widget'] in definePage
```

**Local CSS when global class already covers it:**
```css
/* In YourPage.module.css */
.myPanel { padding: 1rem; background: var(--panel-bg); }
/* But .panel in src/app/styles.css already provides this */
```

**Building a feature the framework already provides:**
```jsx
// New page renders registry cards manually
// But RegistryExplorerPage already does search + filtering
```
