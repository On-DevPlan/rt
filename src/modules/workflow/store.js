import { create } from 'zustand'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'
import { defaultEdgeOptions, NodeType } from '../types'

/**
 * 生成唯一ID
 */
const generateId = (prefix = 'node') => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

/**
 * 创建默认节点
 */
const createDefaultNode = (type, position = { x: 200, y: 200 }) => ({
  id: generateId(),
  type,
  position,
  data: {
    label: getDefaultLabel(type),
    ...getDefaultData(type)
  },
  style: {},
  parentId: null,
  extent: null
})

/**
 * 获取节点默认标签
 */
const getDefaultLabel = (type) => {
  const labels = {
    [NodeType.START]: '开始',
    [NodeType.STEP]: '步骤',
    [NodeType.END]: '结束',
    [NodeType.TEXT]: '文本',
    [NodeType.IMAGE]: '图片',
    [NodeType.OUTPUT]: '输出',
    [NodeType.GROUP]: '分组'
  }
  return labels[type] || '节点'
}

/**
 * 获取节点默认数据
 */
const getDefaultData = (type) => {
  switch (type) {
    case NodeType.TEXT:
      return { content: '请输入文本内容...' }
    case NodeType.IMAGE:
      return { src: '', alt: '图片' }
    case NodeType.OUTPUT:
      return { value: '', placeholder: '输出结果...' }
    case NodeType.GROUP:
      return { title: '分组', collapsed: false, childNodes: [] }
    default:
      return {}
  }
}

const initialNodes = [
  {
    id: 'start_1',
    type: NodeType.START,
    position: { x: 100, y: 300 },
    data: { label: '开始' }
  },
  {
    id: 'step_1',
    type: NodeType.STEP,
    position: { x: 350, y: 300 },
    data: { label: '步骤 1' }
  },
  {
    id: 'end_1',
    type: NodeType.END,
    position: { x: 600, y: 300 },
    data: { label: '结束' }
  }
]

const initialEdges = [
  {
    id: 'e_start_1-step_1',
    source: 'start_1',
    target: 'step_1',
    ...defaultEdgeOptions
  },
  {
    id: 'e_step_1-end_1',
    source: 'step_1',
    target: 'end_1',
    ...defaultEdgeOptions
  }
]

const useWorkflowStore = create((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,

  selectedNodeId: null,
  selectedEdgeId: null,

  viewport: { x: 0, y: 0, zoom: 1 },

  history: {
    nodes: [initialNodes],
    edges: [initialEdges],
    currentIndex: 0
  },

  onNodesChange: (changes) => {
    set(state => ({
      nodes: applyNodeChanges(changes, state.nodes)
    }))
  },

  onEdgesChange: (changes) => {
    set(state => ({
      edges: applyEdgeChanges(changes, state.edges)
    }))
  },

  onConnect: (connection) => {
    set(state => ({
      edges: addEdge({
        ...connection,
        id: generateId('edge'),
        ...defaultEdgeOptions
      }, state.edges)
    }))
  },

  addNode: (type, position = { x: 300, y: 300 }) => {
    const newNode = createDefaultNode(type, position)
    set(state => ({
      nodes: [...state.nodes, newNode],
      selectedNodeId: newNode.id
    }))
    return newNode
  },

  updateNode: (nodeId, updates) => {
    set(state => ({
      nodes: state.nodes.map(n =>
        n.id === nodeId ? { ...n, ...updates, data: { ...n.data, ...updates.data } } : n
      )
    }))
  },

  updateNodeData: (nodeId, dataUpdates) => {
    set(state => ({
      nodes: state.nodes.map(n =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...dataUpdates } } : n
      )
    }))
  },

  deleteNode: (nodeId) => {
    set(state => ({
      nodes: state.nodes.filter(n => n.id !== nodeId),
      edges: state.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
      selectedNodeId: state.selectedNodeId === nodeId ? null : state.selectedNodeId
    }))
  },

  addEdge: (source, target, data = {}) => {
    const newEdge = {
      id: generateId('edge'),
      source,
      target,
      ...defaultEdgeOptions,
      data
    }
    set(state => ({
      edges: [...state.edges, newEdge]
    }))
    return newEdge
  },

  updateEdge: (edgeId, updates) => {
    set(state => ({
      edges: state.edges.map(e =>
        e.id === edgeId ? { ...e, ...updates } : e
      )
    }))
  },

  deleteEdge: (edgeId) => {
    set(state => ({
      edges: state.edges.filter(e => e.id !== edgeId),
      selectedEdgeId: state.selectedEdgeId === edgeId ? null : state.selectedEdgeId
    }))
  },

  setNodes: (nodes) => {
    set({ nodes })
  },

  setEdges: (edges) => {
    set({ edges })
  },

  setSelectedNode: (nodeId) => {
    set({ selectedNodeId: nodeId, selectedEdgeId: null })
  },

  setSelectedEdge: (edgeId) => {
    set({ selectedEdgeId: edgeId, selectedNodeId: null })
  },

  clearSelection: () => {
    set({ selectedNodeId: null, selectedEdgeId: null })
  },

  updateViewport: (viewport) => {
    set({ viewport })
  },

  reset: () => {
    set({
      nodes: initialNodes,
      edges: initialEdges,
      selectedNodeId: null,
      selectedEdgeId: null
    })
  },

  importData: ({ nodes, edges }) => {
    set({ nodes, edges })
  },

  exportData: () => {
    const { nodes, edges } = get()
    return { nodes, edges }
  },

  getNode: (nodeId) => {
    return get().nodes.find(n => n.id === nodeId)
  },

  getEdge: (edgeId) => {
    return get().edges.find(e => e.id === edgeId)
  },

  getSelectedNode: () => {
    const { nodes, selectedNodeId } = get()
    return nodes.find(n => n.id === selectedNodeId)
  },

  getSelectedEdge: () => {
    const { edges, selectedEdgeId } = get()
    return edges.find(e => e.id === selectedEdgeId)
  }
}))

export default useWorkflowStore
