import { NodeType } from '../../types'
import StartNode from './StartNode'
import EndNode from './EndNode'
import StepNode from './StepNode'
import TextNode from './TextNode'
import ImageNode from './ImageNode'
import OutputNode from './OutputNode'
import GroupNode from './GroupNode'

/**
 * 节点类型注册表
 */
const nodeTypes = {
  [NodeType.START]: StartNode,
  [NodeType.STEP]: StepNode,
  [NodeType.END]: EndNode,
  [NodeType.TEXT]: TextNode,
  [NodeType.IMAGE]: ImageNode,
  [NodeType.OUTPUT]: OutputNode,
  [NodeType.GROUP]: GroupNode
}

export { NodeType }

export default nodeTypes

/**
 * 获取节点类型列表（用于工具栏）
 */
export const nodeTypeList = [
  { type: NodeType.START, label: '开始', icon: '▶', color: '#52c41a' },
  { type: NodeType.STEP, label: '步骤', icon: '◆', color: '#1890ff' },
  { type: NodeType.END, label: '结束', icon: '■', color: '#ff4d4f' },
  { type: NodeType.TEXT, label: '文本', icon: 'T', color: '#722ed1' },
  { type: NodeType.IMAGE, label: '图片', icon: '▣', color: '#eb2f96' },
  { type: NodeType.OUTPUT, label: '输出', icon: '⬡', color: '#faad14' },
  { type: NodeType.GROUP, label: '分组', icon: '☰', color: '#13c2c2' }
]
