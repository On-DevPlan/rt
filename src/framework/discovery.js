import { lazy } from 'react'

const metaModules = import.meta.glob('../modules/**/module.meta.js', { eager: true })
const pageModules = import.meta.glob('../modules/**/pages/**/*.{js,jsx}')
const widgetModules = import.meta.glob('../modules/**/widgets/**/*.{js,jsx}')

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
    order: meta.order || 0,
    color: meta.color || '#1e7a5d',
    pages: ensureArray(meta.pages),
    widgets: ensureArray(meta.widgets)
  }
}

export function createRegistry() {
  const modules = []
  const pages = []
  const widgets = []
  const pageIdSet = new Set()
  const routeSet = new Set()
  const widgetIdSet = new Set()

  for (const [metaPath, moduleExports] of Object.entries(metaModules)) {
    const moduleMeta = normalizeModule(metaPath, moduleExports.default || moduleExports)
    const moduleRoot = moduleRootFromMetaPath(metaPath)
    const moduleRecord = {
      ...moduleMeta,
      pageIds: [],
      widgetIds: []
    }

    for (const pageMeta of moduleMeta.pages) {
      const pageId = pageMeta.id || `${moduleMeta.id}-${moduleRecord.pageIds.length + 1}`
      const route = ensureLeadingSlash(pageMeta.route || `${moduleMeta.id}/${pageId}`)
      const entryPath = resolveEntryPath(moduleRoot, pageMeta.entry)
      const loader = pageModules[entryPath]

      if (!loader) {
        throw new Error(`Missing page entry for "${pageId}": ${entryPath}`)
      }

      if (pageIdSet.has(pageId)) {
        throw new Error(`Duplicated page id "${pageId}"`)
      }

      if (routeSet.has(route)) {
        throw new Error(`Duplicated route "${route}"`)
      }

      pageIdSet.add(pageId)
      routeSet.add(route)

      const cachedLoader = createCachedLoader(loader, entryPath)

      pages.push({
        id: pageId,
        moduleId: moduleMeta.id,
        moduleTitle: moduleMeta.title,
        title: pageMeta.title || pageId,
        route,
        summary: pageMeta.summary || '',
        order: pageMeta.order || 0,
        tags: ensureArray(pageMeta.tags),
        widgets: ensureArray(pageMeta.widgets),
        entry: pageMeta.entry,
        preload: cachedLoader.preload,
        Component: lazy(cachedLoader)
      })

      moduleRecord.pageIds.push(pageId)
    }

    for (const widgetMeta of moduleMeta.widgets) {
      const widgetId = widgetMeta.id || `${moduleMeta.id}-widget-${moduleRecord.widgetIds.length + 1}`
      const entryPath = resolveEntryPath(moduleRoot, widgetMeta.entry)
      const loader = widgetModules[entryPath]

      if (!loader) {
        throw new Error(`Missing widget entry for "${widgetId}": ${entryPath}`)
      }

      if (widgetIdSet.has(widgetId)) {
        throw new Error(`Duplicated widget id "${widgetId}"`)
      }

      widgetIdSet.add(widgetId)

      const cachedLoader = createCachedLoader(loader, entryPath)

      widgets.push({
        id: widgetId,
        moduleId: moduleMeta.id,
        moduleTitle: moduleMeta.title,
        title: widgetMeta.title || widgetId,
        summary: widgetMeta.summary || '',
        order: widgetMeta.order || 0,
        tags: ensureArray(widgetMeta.tags),
        entry: widgetMeta.entry,
        preload: cachedLoader.preload,
        Component: lazy(cachedLoader)
      })

      moduleRecord.widgetIds.push(widgetId)
    }

    modules.push(moduleRecord)
  }

  const sortedModules = sortByOrder(modules).map((moduleRecord) => ({
    ...moduleRecord,
    pageIds: sortByOrder(
      moduleRecord.pageIds
        .map((pageId) => pages.find((page) => page.id === pageId))
        .filter(Boolean)
    ).map((page) => page.id),
    widgetIds: sortByOrder(
      moduleRecord.widgetIds
        .map((widgetId) => widgets.find((widget) => widget.id === widgetId))
        .filter(Boolean)
    ).map((widget) => widget.id)
  }))
  const sortedPages = sortByOrder(pages)
  const sortedWidgets = sortByOrder(widgets)

  return {
    modules: sortedModules,
    pages: sortedPages,
    widgets: sortedWidgets,
    modulesById: new Map(sortedModules.map((item) => [item.id, item])),
    pagesById: new Map(sortedPages.map((item) => [item.id, item])),
    widgetsById: new Map(sortedWidgets.map((item) => [item.id, item])),
    stats: {
      moduleCount: sortedModules.length,
      pageCount: sortedPages.length,
      widgetCount: sortedWidgets.length,
      routeCount: sortedPages.length
    }
  }
}
