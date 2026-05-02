/**
 * 节点类型枚举
 */
export const NodeType = {
  START: 'start',
  STEP: 'step',
  END: 'end',
  TEXT: 'text',
  IMAGE: 'image',
  OUTPUT: 'output',
  GROUP: 'group'
}

/**
 * 边的默认配置
 */
export const defaultEdgeOptions = {
  animated: true,
  markerEnd: {
    type: 'ArrowClosed'
  }
}

/**
 * 应用节点类型定义
 */
export const AppNode = {
  id: '',
  type: '',
  position: { x: 0, y: 0 },
  data: {},
  style: {},
  targetPosition: 'left',
  sourcePosition: 'right'
}

/**
 * 应用边类型定义
 */
export const AppEdge = {
  id: '',
  source: '',
  target: '',
  type: 'fmEdge',
  animated: false,
  data: {}
}

/**
 * 节点变更类型
 */
export const ChangeType = {
  POSITION: 'position',
  DIMENSION: 'dimension',
  SELECTION: 'selection',
  REMOVING: 'removing',
  ADDING: 'adding'
}

/**
 * 图论操作结果
 */
export const GraphResult = {
  nodes: [],
  edges: []
}
