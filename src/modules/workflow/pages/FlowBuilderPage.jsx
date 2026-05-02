import { useCallback, useState } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import styles from './FlowBuilderPage.module.css'

const nodeTypes = {
  start: ({ data }) => (
    <div className={styles.nodeStart}>
      <span>{data.label}</span>
    </div>
  ),
  step: ({ data }) => (
    <div className={styles.nodeStep}>
      <span>{data.label}</span>
    </div>
  ),
  end: ({ data }) => (
    <div className={styles.nodeEnd}>
      <span>{data.label}</span>
    </div>
  )
}

const edgeOptions = {
  animated: true,
  markerEnd: {
    type: MarkerType.ArrowClosed,
    width: 20,
    height: 20
  }
}

const initialNodes = [
  {
    id: '1',
    type: 'start',
    position: { x: 100, y: 200 },
    data: { label: 'Start' }
  },
  {
    id: '2',
    type: 'step',
    position: { x: 300, y: 200 },
    data: { label: 'Step 1' }
  },
  {
    id: '3',
    type: 'step',
    position: { x: 500, y: 200 },
    data: { label: 'Step 2' }
  },
  {
    id: '4',
    type: 'end',
    position: { x: 700, y: 200 },
    data: { label: 'End' }
  }
]

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', ...edgeOptions },
  { id: 'e2-3', source: '2', target: '3', ...edgeOptions },
  { id: 'e3-4', source: '3', target: '4', ...edgeOptions }
]

export default function FlowBuilderPage() {
  const [nodes, setNodes] = useState(initialNodes)
  const [edges, setEdges] = useState(initialEdges)

  const onNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  )
  const onEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  )
  const onConnect = useCallback(
    (connection) => setEdges((eds) => addEdge({ ...connection, ...edgeOptions }, eds)),
    []
  )

  const addNode = (type) => {
    const id = `${Date.now()}`
    const newNode = {
      id,
      type,
      position: { x: 400, y: 300 },
      data: { label: type === 'start' ? 'Start' : type === 'end' ? 'End' : 'New Step' }
    }
    setNodes((nds) => [...nds, newNode])
  }

  const clearAll = () => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }

  return (
    <div className="page-stack">
      <section className={styles.shell}>
        <header className={styles.header}>
          <div>
            <h2>Flow Builder</h2>
            <p>Drag nodes to design your workflow</p>
          </div>
          <div className={styles.toolbar}>
            <button className={styles.btnPrimary} onClick={() => addNode('step')}>+ Step</button>
            <button className={styles.btnDefault} onClick={clearAll}>Reset</button>
          </div>
        </header>

        <div className={styles.canvas}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
          >
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                switch (node.type) {
                  case 'start': return '#52c41a'
                  case 'end': return '#ff4d4f'
                  default: return '#1890ff'
                }
              }}
            />
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
          </ReactFlow>
        </div>

        <div className={styles.info}>
          <strong>Nodes:</strong> {nodes.length} &nbsp;|&nbsp; <strong>Edges:</strong> {edges.length}
        </div>
      </section>
    </div>
  )
}
