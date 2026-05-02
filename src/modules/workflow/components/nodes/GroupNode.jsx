import { Handle, Position } from '@xyflow/react'
import { NodeResizer } from '@xyflow/react'

/**
 * 分组节点（支持嵌套）
 */
function GroupNode({ data, selected, children }) {
  const { title = '分组', collapsed = false, style = {} } = data || {}

  return (
    <NodeResizer
      minWidth={200}
      minHeight={150}
      isVisible={selected}
      lineStyle={{ borderColor: '#1890ff' }}
      handleStyle={{ width: 10, height: 10 }}
    >
      <div
        className={`workflow-node workflow-node--group ${selected ? 'workflow-node--selected' : ''} ${collapsed ? 'workflow-node--collapsed' : ''}`}
        style={{
          backgroundColor: style.backgroundColor || '#f0f5ff',
          borderColor: style.borderColor || '#1890ff'
        }}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--target"
        />
        <div className="workflow-node__content">
          <div className="workflow-node__header workflow-node__header--group">
            <span className="workflow-node__icon">☰</span>
            <span className="workflow-node__title">{title}</span>
            {collapsed && <span className="workflow-node__badge">已折叠</span>}
          </div>
          {!collapsed && (
            <div className="workflow-node__body workflow-node__group-body">
              {children || (
                <div className="workflow-node__placeholder">
                  拖拽节点到这里
                </div>
              )}
            </div>
          )}
        </div>
        <Handle
          type="source"
          position={Position.Right}
          className="workflow-handle workflow-handle--source"
        />
      </div>
    </NodeResizer>
  )
}

export default GroupNode
