import { Handle, Position } from '@xyflow/react'

/**
 * 结束节点
 */
function EndNode({ data, selected }) {
  return (
    <div className="workflow-node workflow-node--end">
      <Handle
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--target"
      />
      <div className="workflow-node__content">
        <span className="workflow-node__icon">■</span>
        <span className="workflow-node__label">{data.label}</span>
      </div>
    </div>
  )
}

export default EndNode
