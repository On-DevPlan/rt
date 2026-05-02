import { Handle, Position } from '@xyflow/react'

/**
 * 步骤节点
 */
function StepNode({ data, selected }) {
  return (
    <div className={`workflow-node workflow-node--step ${selected ? 'workflow-node--selected' : ''}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--target"
      />
      <div className="workflow-node__content">
        <span className="workflow-node__icon">◆</span>
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

export default StepNode
