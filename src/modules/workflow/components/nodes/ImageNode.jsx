import { Handle, Position } from '@xyflow/react'

/**
 * 图片节点
 */
function ImageNode({ data, selected }) {
  const { src = '', alt = '图片', style = {} } = data || {}

  return (
    <div className={`workflow-node workflow-node--image ${selected ? 'workflow-node--selected' : ''}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--target"
      />
      <div className="workflow-node__content">
        <div className="workflow-node__header">
          <span className="workflow-node__icon">▣</span>
          <span className="workflow-node__type">图片</span>
        </div>
        <div className="workflow-node__body workflow-node__image-wrapper">
          {src ? (
            <img
              src={src}
              alt={alt}
              className="workflow-node__image"
              style={{
                borderRadius: style.borderRadius || '8px',
                objectFit: style.objectFit || 'cover'
              }}
            />
          ) : (
            <div className="workflow-node__image-placeholder">
              <span>📷</span>
              <span>点击添加图片</span>
            </div>
          )}
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

export default ImageNode
