import { useReducer, useCallback } from 'react'
import { applyNodeChanges, applyEdgeChanges, addEdge } from '@xyflow/react'
import { defaultEdgeOptions, NodeType } from './types'

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

const initialState = {
  nodes: initialNodes,
  edges: initialEdges,
  selectedNodeId: null,
  selectedEdgeId: null,
  viewport: { x: 0, y: 0, zoom: 1 }
}

/**
 * Reducer actions
 */
const ActionType = {
  NODES_CHANGE: 'NODES_CHANGE',
  EDGES_CHANGE: 'EDGES_CHANGE',
  CONNECT: 'CONNECT',
  ADD_NODE: 'ADD_NODE',
  UPDATE_NODE: 'UPDATE_NODE',
  UPDATE_NODE_DATA: 'UPDATE_NODE_DATA',
  DELETE_NODE: 'DELETE_NODE',
  ADD_EDGE: 'ADD_EDGE',
  UPDATE_EDGE: 'UPDATE_EDGE',
  DELETE_EDGE: 'DELETE_EDGE',
  SET_SELECTED_NODE: 'SET_SELECTED_NODE',
  SET_SELECTED_EDGE: 'SET_SELECTED_EDGE',
  CLEAR_SELECTION: 'CLEAR_SELECTION',
  SET_NODES: 'SET_NODES',
  SET_EDGES: 'SET_EDGES',
  UPDATE_VIEWPORT: 'UPDATE_VIEWPORT',
  RESET: 'RESET',
  IMPORT_DATA: 'IMPORT_DATA'
}

function reducer(state, action) {
  switch (action.type) {
    case ActionType.NODES_CHANGE:
      return {
        ...state,
        nodes: applyNodeChanges(action.payload, state.nodes)
      }

    case ActionType.EDGES_CHANGE:
      return {
        ...state,
        edges: applyEdgeChanges(action.payload, state.edges)
      }

    case ActionType.CONNECT:
      return {
        ...state,
        edges: addEdge({
          ...action.payload,
          id: generateId('edge'),
          ...defaultEdgeOptions
        }, state.edges)
      }

    case ActionType.ADD_NODE: {
      const { type, position } = action.payload
      const newNode = createDefaultNode(type, position)
      return {
        ...state,
        nodes: [...state.nodes, newNode],
        selectedNodeId: newNode.id
      }
    }

    case ActionType.UPDATE_NODE: {
      const { nodeId, updates } = action.payload
      return {
        ...state,
        nodes: state.nodes.map(n =>
          n.id === nodeId
            ? { ...n, ...updates, data: { ...n.data, ...(updates.data || {}) } }
            : n
        )
      }
    }

    case ActionType.UPDATE_NODE_DATA: {
      const { nodeId, dataUpdates } = action.payload
      return {
        ...state,
        nodes: state.nodes.map(n =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, ...dataUpdates } }
            : n
        )
      }
    }

    case ActionType.DELETE_NODE:
      return {
        ...state,
        nodes: state.nodes.filter(n => n.id !== action.payload),
        edges: state.edges.filter(e => e.source !== action.payload && e.target !== action.payload),
        selectedNodeId: state.selectedNodeId === action.payload ? null : state.selectedNodeId
      }

    case ActionType.ADD_EDGE: {
      const { source, target, data } = action.payload
      const newEdge = {
        id: generateId('edge'),
        source,
        target,
        ...defaultEdgeOptions,
        data: data || {}
      }
      return {
        ...state,
        edges: [...state.edges, newEdge]
      }
    }

    case ActionType.UPDATE_EDGE: {
      const { edgeId, updates } = action.payload
      return {
        ...state,
        edges: state.edges.map(e =>
          e.id === edgeId ? { ...e, ...updates } : e
        )
      }
    }

    case ActionType.DELETE_EDGE:
      return {
        ...state,
        edges: state.edges.filter(e => e.id !== action.payload),
        selectedEdgeId: state.selectedEdgeId === action.payload ? null : state.selectedEdgeId
      }

    case ActionType.SET_SELECTED_NODE:
      return {
        ...state,
        selectedNodeId: action.payload,
        selectedEdgeId: null
      }

    case ActionType.SET_SELECTED_EDGE:
      return {
        ...state,
        selectedEdgeId: action.payload,
        selectedNodeId: null
      }

    case ActionType.CLEAR_SELECTION:
      return {
        ...state,
        selectedNodeId: null,
        selectedEdgeId: null
      }

    case ActionType.SET_NODES:
      return { ...state, nodes: action.payload }

    case ActionType.SET_EDGES:
      return { ...state, edges: action.payload }

    case ActionType.UPDATE_VIEWPORT:
      return { ...state, viewport: action.payload }

    case ActionType.RESET:
      return {
        ...initialState,
        nodes: initialNodes,
        edges: initialEdges
      }

    case ActionType.IMPORT_DATA: {
      const { nodes, edges } = action.payload
      return { ...state, nodes, edges }
    }

    default:
      return state
  }
}

/**
 * Store hook
 */
export function useWorkflowStore() {
  const [state, dispatch] = useReducer(reducer, initialState)

  const onNodesChange = useCallback((changes) => {
    dispatch({ type: ActionType.NODES_CHANGE, payload: changes })
  }, [])

  const onEdgesChange = useCallback((changes) => {
    dispatch({ type: ActionType.EDGES_CHANGE, payload: changes })
  }, [])

  const onConnect = useCallback((connection) => {
    dispatch({ type: ActionType.CONNECT, payload: connection })
  }, [])

  const addNode = useCallback((type, position = { x: 300, y: 300 }) => {
    dispatch({ type: ActionType.ADD_NODE, payload: { type, position } })
  }, [])

  const updateNode = useCallback((nodeId, updates) => {
    dispatch({ type: ActionType.UPDATE_NODE, payload: { nodeId, updates } })
  }, [])

  const updateNodeData = useCallback((nodeId, dataUpdates) => {
    dispatch({ type: ActionType.UPDATE_NODE_DATA, payload: { nodeId, dataUpdates } })
  }, [])

  const deleteNode = useCallback((nodeId) => {
    dispatch({ type: ActionType.DELETE_NODE, payload: nodeId })
  }, [])

  const addEdge = useCallback((source, target, data) => {
    dispatch({ type: ActionType.ADD_EDGE, payload: { source, target, data } })
  }, [])

  const updateEdge = useCallback((edgeId, updates) => {
    dispatch({ type: ActionType.UPDATE_EDGE, payload: { edgeId, updates } })
  }, [])

  const deleteEdge = useCallback((edgeId) => {
    dispatch({ type: ActionType.DELETE_EDGE, payload: edgeId })
  }, [])

  const setNodes = useCallback((nodes) => {
    dispatch({ type: ActionType.SET_NODES, payload: nodes })
  }, [])

  const setEdges = useCallback((edges) => {
    dispatch({ type: ActionType.SET_EDGES, payload: edges })
  }, [])

  const setSelectedNode = useCallback((nodeId) => {
    dispatch({ type: ActionType.SET_SELECTED_NODE, payload: nodeId })
  }, [])

  const setSelectedEdge = useCallback((edgeId) => {
    dispatch({ type: ActionType.SET_SELECTED_EDGE, payload: edgeId })
  }, [])

  const clearSelection = useCallback(() => {
    dispatch({ type: ActionType.CLEAR_SELECTION })
  }, [])

  const updateViewport = useCallback((viewport) => {
    dispatch({ type: ActionType.UPDATE_VIEWPORT, payload: viewport })
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: ActionType.RESET })
  }, [])

  const importData = useCallback(({ nodes, edges }) => {
    dispatch({ type: ActionType.IMPORT_DATA, payload: { nodes, edges } })
  }, [])

  const exportData = useCallback(() => {
    return { nodes: state.nodes, edges: state.edges }
  }, [state.nodes, state.edges])

  const getNode = useCallback((nodeId) => {
    return state.nodes.find(n => n.id === nodeId)
  }, [state.nodes])

  const getEdge = useCallback((edgeId) => {
    return state.edges.find(e => e.id === edgeId)
  }, [state.edges])

  const getSelectedNode = useCallback(() => {
    return state.nodes.find(n => n.id === state.selectedNodeId)
  }, [state.nodes, state.selectedNodeId])

  const getSelectedEdge = useCallback(() => {
    return state.edges.find(e => e.id === state.selectedEdgeId)
  }, [state.edges, state.selectedEdgeId])

  return {
    nodes: state.nodes,
    edges: state.edges,
    selectedNodeId: state.selectedNodeId,
    selectedEdgeId: state.selectedEdgeId,
    viewport: state.viewport,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    updateNode,
    updateNodeData,
    deleteNode,
    addEdge,
    updateEdge,
    deleteEdge,
    setNodes,
    setEdges,
    setSelectedNode,
    setSelectedEdge,
    clearSelection,
    updateViewport,
    reset,
    importData,
    exportData,
    getNode,
    getEdge,
    getSelectedNode,
    getSelectedEdge
  }
}

export default useWorkflowStore
