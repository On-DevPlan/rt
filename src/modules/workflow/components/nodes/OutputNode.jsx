import { Handle, Position } from '@xyflow/react'

/**
 * 输出节点
 */
function OutputNode({ data, selected }) {
  const { value = '', placeholder = '输出结果...', style = {} } = data || {}

  return (
    <div className={`workflow-node workflow-node--output ${selected ? 'workflow-node--selected' : ''}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--target"
      />
      <div className="workflow-node__content">
        <div className="workflow-node__header">
          <span className="workflow-node__icon">⬡</span>
          <span className="workflow-node__type">输出</span>
        </div>
        <div className="workflow-node__body workflow-node__output-wrapper">
          <div
            className="workflow-node__output"
            style={{
              backgroundColor: style.backgroundColor || '#f5f5f5',
              borderColor: style.borderColor || '#d9d9d9'
            }}
          >
            {value || placeholder}
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--source"
      />
    </div>
  )
}

export default OutputNode
