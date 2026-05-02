import { useState, useEffect } from 'react'
import useWorkflowStore from '../store'
import { NodeType } from '../types'
import {
  getOutgoingNodes,
  getIncomingNodes,
  getRootNodes,
  getLeafNodes
} from '../utils/graph'
import styles from './PropertiesPanel.module.css'

/**
 * 属性面板组件
 */
function PropertiesPanel() {
  const {
    selectedNodeId,
    nodes,
    edges,
    getNode,
    updateNodeData,
    deleteNode
  } = useWorkflowStore()

  const [localData, setLocalData] = useState({})

  const selectedNode = selectedNodeId ? getNode(selectedNodeId) : null

  useEffect(() => {
    if (selectedNode) {
      setLocalData(selectedNode.data || {})
    }
  }, [selectedNode])

  if (!selectedNode) {
    return (
      <div className={`${styles.panel} ${styles.empty}`}>
        <div className={styles.emptyContent}>
          <span>选择一个节点</span>
          <span>查看属性</span>
        </div>
      </div>
    )
  }

  const handleChange = (key, value) => {
    const newData = { ...localData, [key]: value }
    setLocalData(newData)
    updateNodeData(selectedNodeId, newData)
  }

  const handleDelete = () => {
    deleteNode(selectedNodeId)
  }

  const outgoing = getOutgoingNodes(selectedNodeId, nodes, edges)
  const incoming = getIncomingNodes(selectedNodeId, nodes, edges)
  const rootNodes = getRootNodes(nodes, edges)
  const leafNodes = getLeafNodes(nodes, edges)
  const isRoot = rootNodes.some(n => n.id === selectedNodeId)
  const isLeaf = leafNodes.some(n => n.id === selectedNodeId)

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h4>节点属性</h4>
        <span className={styles.type}>{selectedNode.type}</span>
      </div>

      <div className={styles.body}>
        <div className={styles.section}>
          <label className={styles.label}>ID</label>
          <input
            type="text"
            className={styles.input}
            value={selectedNode.id}
            disabled
          />
        </div>

        <div className={styles.section}>
          <label className={styles.label}>标签</label>
          <input
            type="text"
            className={styles.input}
            value={localData.label || ''}
            onChange={(e) => handleChange('label', e.target.value)}
          />
        </div>

        {selectedNode.type === NodeType.TEXT && (
          <div className={styles.section}>
            <label className={styles.label}>内容</label>
            <textarea
              className={styles.textarea}
              value={localData.content || ''}
              onChange={(e) => handleChange('content', e.target.value)}
              rows={4}
            />
          </div>
        )}

        {selectedNode.type === NodeType.IMAGE && (
          <>
            <div className={styles.section}>
              <label className={styles.label}>图片地址</label>
              <input
                type="text"
                className={styles.input}
                value={localData.src || ''}
                onChange={(e) => handleChange('src', e.target.value)}
                placeholder="输入图片URL"
              />
            </div>
            <div className={styles.section}>
              <label className={styles.label}>alt文字</label>
              <input
                type="text"
                className={styles.input}
                value={localData.alt || ''}
                onChange={(e) => handleChange('alt', e.target.value)}
              />
            </div>
          </>
        )}

        {selectedNode.type === NodeType.OUTPUT && (
          <>
            <div className={styles.section}>
              <label className={styles.label}>输出值</label>
              <input
                type="text"
                className={styles.input}
                value={localData.value || ''}
                onChange={(e) => handleChange('value', e.target.value)}
                placeholder="输出结果"
              />
            </div>
            <div className={styles.section}>
              <label className={styles.label}>占位符</label>
              <input
                type="text"
                className={styles.input}
                value={localData.placeholder || ''}
                onChange={(e) => handleChange('placeholder', e.target.value)}
              />
            </div>
          </>
        )}

        {selectedNode.type === NodeType.GROUP && (
          <>
            <div className={styles.section}>
              <label className={styles.label}>分组标题</label>
              <input
                type="text"
                className={styles.input}
                value={localData.title || ''}
                onChange={(e) => handleChange('title', e.target.value)}
              />
            </div>
            <div className={styles.section}>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={localData.collapsed || false}
                  onChange={(e) => handleChange('collapsed', e.target.checked)}
                />
                折叠
              </label>
            </div>
          </>
        )}
      </div>

      <div className={styles.graph}>
        <h5>图论信息</h5>
        <div className={styles.graphItem}>
          <span>类型:</span>
          <span>{isRoot ? '根节点' : isLeaf ? '叶节点' : '中间节点'}</span>
        </div>
        <div className={styles.graphItem}>
          <span>入度:</span>
          <span>{incoming.length}</span>
        </div>
        <div className={styles.graphItem}>
          <span>出度:</span>
          <span>{outgoing.length}</span>
        </div>
      </div>

      <div className={styles.footer}>
        <button
          className={`${styles.btn} ${styles.deleteBtn}`}
          onClick={handleDelete}
        >
          删除节点
        </button>
      </div>
    </div>
  )
}

export default PropertiesPanel
