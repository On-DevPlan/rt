export function defineModule(config) {
  return config
}

export function definePage(config) {
  return {
    order: 0,
    tags: [],
    widgets: [],
    showcase: true,
    fullscreen: true,
    internal: false,
    ...config
  }
}

export function defineWidget(config) {
  return {
    order: 0,
    tags: [],
    ...config
  }
}
