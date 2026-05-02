# RT Component Rules

## 1. Core model

This project does not use a central route table or a global component registry file.
It uses a manifest-driven module model:

- One module maps to one folder under `src/modules/<module-id>/`
- One module must have exactly one `module.meta.js`
- Pages live under `pages/`
- Mountable side widgets live under `widgets/`
- Auto-discovery reads metadata first, then lazy-loads page/widget code

The important consequence:

- Register metadata only after the target file already exists
- A wrong `entry` path breaks registry creation during startup

## 2. Folder contract

Standard module shape:

```text
src/modules/<module-id>/
  module.meta.js
  pages/
    SomePage.jsx
  widgets/
    SomeWidget.jsx
```

Rules:

- Use lowercase kebab-like folder naming for modules when possible: `reading`, `lab`, `orders`
- Keep `module.meta.js` at module root only
- Put route pages only in `pages/`
- Put page-side reusable blocks only in `widgets/`
- Do not put registration metadata inside page files
- Do not import page files manually into `App.jsx`

## 3. What counts as a component here

In this project, "component" has three different levels:

1. Module
   A business or feature boundary. Example: `reading`
2. Page
   A route-level screen declared in `module.meta.js`
3. Widget
   A lazily mounted panel-like component referenced by a page

Use these boundaries correctly:

- Add a `page` when the feature needs its own route
- Add a `widget` when the feature is mounted inside a page sidebar or slot
- Add plain internal React components inside a page file or a local sibling file when they do not need registry visibility

## 4. Required metadata fields

`defineModule(...)` should provide:

- `id`
- `title`
- `description`
- `order`
- `pages`
- `widgets`

`definePage(...)` should provide at least:

- `id`
- `title`
- `route`
- `entry`
- `summary`

Optional but recommended:

- `order`
- `tags`
- `widgets`

`defineWidget(...)` should provide at least:

- `id`
- `title`
- `entry`
- `summary`

Optional but recommended:

- `order`
- `tags`

## 5. File creation order

When adding a new page component, use this order:

1. Choose the target module
   If no existing module fits, create a new module folder first.
2. Create the runtime file first
   Add `pages/<Name>Page.jsx` or `widgets/<Name>Widget.jsx` before editing metadata.
3. Implement the component export
   Use `export default function ...`.
4. Add or update `module.meta.js`
   Register `entry`, `route`, `id`, `summary`, and related tags.
5. Attach widgets from the page declaration
   Use `widgets: ['widget-id']` only after the widget exists and is registered.
6. Add styles
   Prefer project-level styles only when the component introduces reusable visual language.
7. Build immediately
   Run `pnpm run build`.

Why this order matters:

- `src/framework/discovery.js` resolves `entry` paths eagerly against glob maps
- If metadata points to a missing file, startup throws immediately

## 6. Naming rules

Use consistent names across folder, id, route, and file:

- Module folder: `reading`
- Module id: `reading`
- Page id: `story-reader`
- Route: `/reading/story`
- Page file: `SentenceReaderPage.jsx`
- Widget id: `route-map`
- Widget file: `RouteMapWidget.jsx`

Prefer:

- Page files ending with `Page.jsx`
- Widget files ending with `Widget.jsx`
- Route paths beginning with module namespace
- Stable ids; avoid renaming ids casually after other pages start referencing them

## 7. Coding rules

Component file rules:

- Default export exactly one React component
- Keep top-level side effects out of page/widget modules
- Keep data local unless the feature truly needs shared state
- Use small local helper components inside the page file first
- Split files only when the page becomes hard to read

Registry rules:

- Never duplicate page `id`
- Never duplicate widget `id`
- Never duplicate page `route`
- Never point `entry` to the wrong directory
- Never register a widget in page metadata before the widget is registered in module metadata

UI rules:

- Make new pages visually intentional, not placeholder gray boxes
- Keep responsive behavior working on desktop and mobile
- Prefer explicit loading / waiting states for async behavior

## 8. Recommended patterns

### Add a new page to an existing module

1. Create `src/modules/<module>/pages/NewFeaturePage.jsx`
2. Export the page component
3. Add a `definePage(...)` entry in `module.meta.js`
4. Build and verify the route appears in sidebar navigation

### Add a page plus a sidebar widget

1. Create `pages/NewFeaturePage.jsx`
2. Create `widgets/NewFeatureWidget.jsx`
3. Add `defineWidget(...)` first or together
4. Reference widget id from the page `widgets` array
5. Build and open the page

### Add a brand new module

1. Create `src/modules/<module-id>/`
2. Create `module.meta.js`
3. Create `pages/`
4. Create the first page file
5. Register the page
6. Build

## 9. Good example

```text
src/modules/reading/
  module.meta.js
  pages/
    SentenceReaderPage.jsx
```

Good because:

- Route page exists before registration
- `entry` points to `./pages/SentenceReaderPage.jsx`
- Module boundary is clear
- Route namespace matches module namespace

## 10. bad_eg

### bad_eg 1: Register before file exists

```js
definePage({
  id: 'voice-reader',
  route: '/reading/voice',
  entry: './pages/VoiceReaderPage.jsx'
})
```

But `src/modules/reading/pages/VoiceReaderPage.jsx` does not exist yet.

Result:

- `createRegistry()` throws during startup
- App fails before route render

### bad_eg 2: Put widget file under `pages/`

```text
src/modules/reading/pages/ReadingToolbarWidget.jsx
```

And then:

```js
defineWidget({
  id: 'reading-toolbar',
  entry: './pages/ReadingToolbarWidget.jsx'
})
```

This is structurally wrong.

Why bad:

- It breaks the page/widget separation
- Future maintainers cannot tell route components from mountable widgets

### bad_eg 3: Duplicate route

```js
definePage({
  id: 'story-reader-v2',
  route: '/reading/story',
  entry: './pages/StoryReaderV2Page.jsx'
})
```

If another page already owns `/reading/story`, discovery throws.

### bad_eg 4: Duplicate widget id across modules

```js
defineWidget({
  id: 'route-map',
  entry: './widgets/AnotherRouteMapWidget.jsx'
})
```

If `route-map` already exists elsewhere, registry throws.

### bad_eg 5: Bypass manifest and import page manually

```jsx
import SomePage from '../modules/demo/pages/SomePage.jsx'
```

Then manually wire it into app routing.

Why bad:

- It defeats the framework contract
- Sidebar, preload, and registry stats stop being the single source of truth

### bad_eg 6: Use unstable ids

```js
definePage({
  id: `reader-${Date.now()}`,
  route: '/reading/story',
  entry: './pages/SentenceReaderPage.jsx'
})
```

Why bad:

- Ids must be deterministic
- References from page `widgets` and debug tooling depend on stability

## 11. Minimal checklist before commit

- File exists before metadata references it
- `module.meta.js` is at module root
- `entry` path starts with `./pages/` or `./widgets/`
- `id` is unique
- `route` is unique
- Default export exists
- `pnpm run build` passes

## 12. Current recommendation

For this project, prefer this decision order when adding new UI:

1. Is it route-level?
   If yes, make a page.
2. Is it only mounted inside another page?
   If yes, make a widget.
3. Is it only an implementation detail?
   Keep it local and do not register it.

This keeps metadata concentrated and prevents registry noise.
