import { BaseEdge, EdgeLabelRenderer, getBezierPath, useReactFlow } from '@xyflow/react'

/**
 * 自定义边组件
 */
function FmEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected
}) {
  const { setEdges } = useReactFlow()

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition
  })

  const { style = {}, label = '' } = data || {}

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: style.stroke || '#1890ff',
          strokeWidth: style.strokeWidth || 2,
          strokeDasharray: style.strokeDasharray || 'none'
        }}
      />
      {selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all'
            }}
            className="nodrag nopan"
          >
            <div className="edge-label">{label}</div>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

/**
 * 动画边组件
 */
function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data
}) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition
  })

  const { style = {} } = data || {}

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: style.stroke || '#1890ff',
          strokeWidth: style.strokeWidth || 2
        }}
        className="animated-edge"
      />
    </>
  )
}

/**
 * 边类型注册表
 */
const edgeTypes = {
  fmEdge: FmEdge,
  animated: AnimatedEdge
}

export default edgeTypes
