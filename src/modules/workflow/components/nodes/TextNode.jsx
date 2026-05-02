import { Handle, Position } from '@xyflow/react'

/**
 * 文本节点
 */
function TextNode({ data, selected }) {
  const { content = '请输入文本...', style = {} } = data || {}

  return (
    <div className={`workflow-node workflow-node--text ${selected ? 'workflow-node--selected' : ''}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--target"
      />
      <div className="workflow-node__content">
        <div className="workflow-node__header">
          <span className="workflow-node__icon">T</span>
          <span className="workflow-node__type">文本</span>
        </div>
        <div
          className="workflow-node__body workflow-node__text"
          style={{
            color: style.color || '#333',
            fontSize: style.fontSize || '14px',
            fontWeight: style.fontWeight || 'normal',
            textAlign: style.textAlign || 'left'
          }}
        >
          {content}
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

export default TextNode
