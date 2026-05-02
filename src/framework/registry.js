import { createRegistry } from './discovery.js'

export const registry = createRegistry()

export function getModulePages(moduleId) {
  return registry.pages.filter((page) => page.moduleId === moduleId)
}

export function getModuleWidgets(moduleId) {
  return registry.widgets.filter((widget) => widget.moduleId === moduleId)
}

export function getWidgetById(widgetId) {
  return registry.widgetsById.get(widgetId)
}
