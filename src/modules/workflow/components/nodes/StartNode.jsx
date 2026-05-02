import { Handle, Position } from '@xyflow/react'

/**
 * 开始节点
 */
function StartNode({ data, selected }) {
  return (
    <div className="workflow-node workflow-node--start">
      <div className="workflow-node__content">
        <span className="workflow-node__icon">▶</span>
        <span className="workflow-node__label">{data.label}</span>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--source"
      />
    </div>
  )
}

export default StartNode
