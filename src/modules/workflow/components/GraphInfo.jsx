import useWorkflowStore from '../store'
import {
  getRootNodes,
  getLeafNodes,
  topologicalSort,
  hasCycle
} from '../utils/graph'
import styles from './GraphInfo.module.css'

/**
 * 图信息组件
 */
function GraphInfo() {
  const { nodes, edges } = useWorkflowStore()

  const rootNodes = getRootNodes(nodes, edges)
  const leafNodes = getLeafNodes(nodes, edges)
  const sortedNodes = topologicalSort(nodes, edges)
  const cycle = hasCycle(nodes, edges)

  return (
    <div className={styles.info}>
      <div className={styles.title}>
        <h4>图论信息</h4>
      </div>

      <div className={styles.body}>
        <div className={styles.item}>
          <span className={styles.label}>节点总数</span>
          <span className={styles.value}>{nodes.length}</span>
        </div>

        <div className={styles.item}>
          <span className={styles.label}>边总数</span>
          <span className={styles.value}>{edges.length}</span>
        </div>

        <div className={styles.item}>
          <span className={styles.label}>根节点</span>
          <span className={styles.value}>{rootNodes.length}</span>
        </div>

        <div className={styles.item}>
          <span className={styles.label}>叶节点</span>
          <span className={styles.value}>{leafNodes.length}</span>
        </div>

        <div className={styles.item}>
          <span className={styles.label}>存在环</span>
          <span className={`${styles.value} ${cycle ? styles.warning : ''}`}>
            {cycle ? '是' : '否'}
          </span>
        </div>

        <div className={styles.item}>
          <span className={styles.label}>拓扑序</span>
          <span className={`${styles.value} ${styles.small}`}>
            {sortedNodes.length > 0
              ? sortedNodes.map(n => n.id.split('_')[0]).join(' → ')
              : '-'}
          </span>
        </div>
      </div>

      <div className={styles.roots}>
        <span className={styles.label}>根节点列表:</span>
        <div className={styles.list}>
          {rootNodes.map(n => (
            <span key={n.id} className={styles.tag}>{n.data?.label || n.id}</span>
          ))}
        </div>
      </div>

      <div className={styles.leaves}>
        <span className={styles.label}>叶节点列表:</span>
        <div className={styles.list}>
          {leafNodes.map(n => (
            <span key={n.id} className={styles.tag}>{n.data?.label || n.id}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

export default GraphInfo
