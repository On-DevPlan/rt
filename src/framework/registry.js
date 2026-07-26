import { createRegistry } from './discovery.js'

export const registry = createRegistry()

export function getModulePages(moduleId) {
  return registry.pagesByModuleId.get(moduleId) ?? []
}

export function getModuleWidgets(moduleId) {
  return registry.widgetsByModuleId.get(moduleId) ?? []
}

export function getWidgetById(widgetId) {
  return registry.widgetsById.get(widgetId)
}

export function getShowcasePages() {
  return registry.pages.filter((page) => !page.internal && page.showcase)
}
