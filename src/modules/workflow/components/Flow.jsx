import { useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  SelectionMode,
  useNodesState,
  useEdgesState
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import useWorkflowStore from '../store'
import nodeTypes from './nodes'
import edgeTypes from './edges'
import { defaultEdgeOptions } from '../types'
import {
  getRootNodes,
  getLeafNodes,
  getOutgoingNodes,
  getIncomingNodes
} from '../utils/graph'

const nodeColorByType = {
  start: '#52c41a',
  step: '#1890ff',
  end: '#ff4d4f',
  text: '#722ed1',
  image: '#eb2f96',
  output: '#faad14',
  group: '#13c2c2'
}

/**
 * 主 Flow 组件
 */
function Flow({ fitView = true }) {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    onNodesChange: storeOnNodesChange,
    onEdgesChange: storeOnEdgesChange,
    onConnect: storeOnConnect,
    selectedNodeId,
    setSelectedNode,
    clearSelection
  } = useWorkflowStore()

  const [nodes, setNodes, onNodesChange] = useNodesState(storeNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(storeEdges)

  // Sync store nodes to local state
  useEffect(() => {
    setNodes(storeNodes)
  }, [storeNodes, setNodes])

  useEffect(() => {
    setEdges(storeEdges)
  }, [storeEdges, setEdges])

  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node.id)
  }, [setSelectedNode])

  const onPaneClick = useCallback(() => {
    clearSelection()
  }, [clearSelection])

  const onNodesChangeHandler = useCallback((changes) => {
    onNodesChange(changes)
    storeOnNodesChange(changes)
  }, [onNodesChange, storeOnNodesChange])

  const onEdgesChangeHandler = useCallback((changes) => {
    onEdgesChange(changes)
    storeOnEdgesChange(changes)
  }, [onEdgesChange, storeOnEdgesChange])

  const onConnectHandler = useCallback((connection) => {
    const newEdge = {
      ...connection,
      ...defaultEdgeOptions
    }
    setEdges(eds => [...eds, newEdge])
    storeOnConnect(connection)
  }, [setEdges, storeOnConnect])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChangeHandler}
      onEdgesChange={onEdgesChangeHandler}
      onConnect={onConnectHandler}
      onNodeClick={onNodeClick}
      onPaneClick={onPaneClick}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView={fitView}
      fitViewOptions={{ padding: 0.2 }}
      selectionMode={SelectionMode.Partial}
      minZoom={0.1}
      maxZoom={4}
      defaultEdgeOptions={defaultEdgeOptions}
    >
      <Controls />
      <MiniMap
        nodeColor={(node) => nodeColorByType[node.type] || '#999'}
        nodeStrokeWidth={3}
        zoomable
        pannable
      />
      <Background
        variant={BackgroundVariant.Dots}
        gap={20}
        size={1}
        color="#ccc"
      />
    </ReactFlow>
  )
}

export default Flow
