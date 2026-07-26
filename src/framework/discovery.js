import { lazy } from 'react'

// Discovery contract: only conventionally named entries are collected.
// Helper files under pages/ or widgets/ that don't match stay bundled
// with their importer instead of becoming standalone lazy chunks.
const metaModules = import.meta.glob('../modules/*/module.meta.js', { eager: true })
const pageModules = import.meta.glob('../modules/*/pages/**/*Page.{js,jsx}')
const widgetModules = import.meta.glob('../modules/*/widgets/**/*Widget.{js,jsx}')

// Route '/' belongs to the app-level HomePage, never to a module page.
const RESERVED_ROUTES = new Set(['/'])

function createCachedLoader(loader, key) {
  let pendingPromise

  const load = () => {
    if (!pendingPromise) {
      pendingPromise = Promise.resolve(loader()).then((module) => ({
        default: module.default ?? module
      }))
    }

    return pendingPromise
  }

  load.preload = load
  load.key = key
  return load
}

function ensureArray(value) {
  return Array.isArray(value) ? value : []
}

function ensureLeadingSlash(route) {
  if (!route) {
    return '/'
  }

  return route.startsWith('/') ? route : `/${route}`
}

function moduleRootFromMetaPath(metaPath) {
  return metaPath.replace(/\/module\.meta\.js$/, '')
}

function resolveEntryPath(moduleRoot, entry) {
  return `${moduleRoot}/${String(entry || '').replace(/^\.\//, '')}`
}

function sortByOrder(items) {
  return [...items].sort((left, right) => {
    if (left.order !== right.order) {
      return left.order - right.order
    }

    return left.title.localeCompare(right.title, 'zh-CN')
  })
}

function normalizeModule(metaPath, meta) {
  const id = meta.id || moduleRootFromMetaPath(metaPath).split('/').pop()

  return {
    id,
    title: meta.title || id,
    description: meta.description || '',
    order: meta.order ?? 0,
    color: meta.color || '#1e7a5d',
    pages: ensureArray(meta.pages),
    widgets: ensureArray(meta.widgets)
  }
}

function buildPage({ moduleMeta, moduleRoot, pageMeta, fallbackIndex, problems }) {
  const pageId = pageMeta.id || `${moduleMeta.id}-${fallbackIndex}`
  const route = ensureLeadingSlash(pageMeta.route || `${moduleMeta.id}/${pageId}`)
  const entryPath = resolveEntryPath(moduleRoot, pageMeta.entry)
  const loader = pageModules[entryPath]

  if (!loader) {
    problems.push(
      `[${moduleMeta.id}] page "${pageId}" entry not found: ${entryPath} ` +
        '(file must exist and be named *Page.jsx under pages/)'
    )
    return null
  }

  if (RESERVED_ROUTES.has(route)) {
    problems.push(`[${moduleMeta.id}] page "${pageId}" uses reserved route "${route}"`)
    return null
  }

  const cachedLoader = createCachedLoader(loader, entryPath)

  return {
    id: pageId,
    moduleId: moduleMeta.id,
    moduleTitle: moduleMeta.title,
    title: pageMeta.title || pageId,
    route,
    summary: pageMeta.summary || '',
    order: pageMeta.order ?? 0,
    tags: ensureArray(pageMeta.tags),
    widgets: ensureArray(pageMeta.widgets),
    showcase: pageMeta.showcase !== false,
    fullscreen: pageMeta.fullscreen !== false,
    internal: pageMeta.internal === true,
    entry: pageMeta.entry,
    preload: cachedLoader.preload,
    Component: lazy(cachedLoader)
  }
}

function buildWidget({ moduleMeta, moduleRoot, widgetMeta, fallbackIndex, problems }) {
  const widgetId = widgetMeta.id || `${moduleMeta.id}-widget-${fallbackIndex}`
  const entryPath = resolveEntryPath(moduleRoot, widgetMeta.entry)
  const loader = widgetModules[entryPath]

  if (!loader) {
    problems.push(
      `[${moduleMeta.id}] widget "${widgetId}" entry not found: ${entryPath} ` +
        '(file must exist and be named *Widget.jsx under widgets/)'
    )
    return null
  }

  const cachedLoader = createCachedLoader(loader, entryPath)

  return {
    id: widgetId,
    moduleId: moduleMeta.id,
    moduleTitle: moduleMeta.title,
    title: widgetMeta.title || widgetId,
    summary: widgetMeta.summary || '',
    order: widgetMeta.order ?? 0,
    tags: ensureArray(widgetMeta.tags),
    entry: widgetMeta.entry,
    preload: cachedLoader.preload,
    Component: lazy(cachedLoader)
  }
}

function warnOrphanEntries(registeredEntryPaths) {
  if (!import.meta.env.DEV) {
    return
  }

  const orphans = [...Object.keys(pageModules), ...Object.keys(widgetModules)].filter(
    (path) => !registeredEntryPaths.has(path)
  )

  if (orphans.length > 0) {
    console.warn(
      '[rt-discovery] entry files discovered but not registered in any module.meta.js ' +
        '(they still produce build chunks — register or delete them):\n' +
        orphans.map((path) => `  - ${path}`).join('\n')
    )
  }
}

export function createRegistry() {
  const modules = []
  const pages = []
  const widgets = []
  const seenPageIds = new Set()
  const seenRoutes = new Set()
  const seenWidgetIds = new Set()
  const registeredEntryPaths = new Set()
  const problems = []

  for (const [metaPath, moduleExports] of Object.entries(metaModules)) {
    const moduleMeta = normalizeModule(metaPath, moduleExports.default || moduleExports)
    const moduleRoot = moduleRootFromMetaPath(metaPath)
    const modulePages = []
    const moduleWidgets = []

    moduleMeta.pages.forEach((pageMeta, index) => {
      const page = buildPage({
        moduleMeta,
        moduleRoot,
        pageMeta,
        fallbackIndex: index + 1,
        problems
      })

      if (!page) {
        return
      }

      if (seenPageIds.has(page.id)) {
        problems.push(`[${moduleMeta.id}] duplicated page id "${page.id}"`)
        return
      }

      if (seenRoutes.has(page.route)) {
        problems.push(`[${moduleMeta.id}] duplicated route "${page.route}" (page "${page.id}")`)
        return
      }

      seenPageIds.add(page.id)
      seenRoutes.add(page.route)
      registeredEntryPaths.add(resolveEntryPath(moduleRoot, pageMeta.entry))
      modulePages.push(page)
    })

    moduleMeta.widgets.forEach((widgetMeta, index) => {
      const widget = buildWidget({
        moduleMeta,
        moduleRoot,
        widgetMeta,
        fallbackIndex: index + 1,
        problems
      })

      if (!widget) {
        return
      }

      if (seenWidgetIds.has(widget.id)) {
        problems.push(`[${moduleMeta.id}] duplicated widget id "${widget.id}"`)
        return
      }

      seenWidgetIds.add(widget.id)
      registeredEntryPaths.add(resolveEntryPath(moduleRoot, widgetMeta.entry))
      moduleWidgets.push(widget)
    })

    const sortedModulePages = sortByOrder(modulePages)
    const sortedModuleWidgets = sortByOrder(moduleWidgets)

    pages.push(...sortedModulePages)
    widgets.push(...sortedModuleWidgets)
    modules.push({
      ...moduleMeta,
      pageIds: sortedModulePages.map((page) => page.id),
      widgetIds: sortedModuleWidgets.map((widget) => widget.id)
    })
  }

  if (problems.length > 0) {
    throw new Error(
      `Registry discovery failed with ${problems.length} problem(s):\n` +
        problems.map((problem) => `  - ${problem}`).join('\n')
    )
  }

  warnOrphanEntries(registeredEntryPaths)

  const sortedModules = sortByOrder(modules)
  const sortedPages = sortByOrder(pages)
  const sortedWidgets = sortByOrder(widgets)
  const pagesById = new Map(sortedPages.map((item) => [item.id, item]))
  const widgetsById = new Map(sortedWidgets.map((item) => [item.id, item]))

  return {
    modules: sortedModules,
    pages: sortedPages,
    widgets: sortedWidgets,
    modulesById: new Map(sortedModules.map((item) => [item.id, item])),
    pagesById,
    widgetsById,
    pagesByModuleId: new Map(
      sortedModules.map((item) => [item.id, item.pageIds.map((id) => pagesById.get(id))])
    ),
    widgetsByModuleId: new Map(
      sortedModules.map((item) => [item.id, item.widgetIds.map((id) => widgetsById.get(id))])
    ),
    stats: {
      moduleCount: sortedModules.length,
      pageCount: sortedPages.length,
      widgetCount: sortedWidgets.length,
      routeCount: sortedPages.length
    }
  }
}
