import useWorkflowStore from '../store'
import { nodeTypeList, NodeType } from './nodes'
import styles from './Toolbar.module.css'

/**
 * 工具栏组件
 */
function Toolbar() {
  const { addNode, reset, nodes, edges } = useWorkflowStore()

  const handleAddNode = (type) => {
    const position = {
      x: 200 + Math.random() * 300,
      y: 200 + Math.random() * 200
    }
    addNode(type, position)
  }

  return (
    <div className={styles.toolbar}>
      <div className={styles.title}>
        <h3>工作流编辑器</h3>
      </div>

      <div className={styles.actions}>
        {nodeTypeList.map(({ type, label, icon, color }) => (
          <button
            key={type}
            className={styles.btn}
            onClick={() => handleAddNode(type)}
            style={{ '--btn-color': color }}
          >
            <span className={styles.icon}>{icon}</span>
            <span className={styles.label}>{label}</span>
          </button>
        ))}
      </div>

      <div className={styles.info}>
        <span>节点: {nodes.length}</span>
        <span>连线: {edges.length}</span>
      </div>

      <button
        className={`${styles.btn} ${styles.reset}`}
        onClick={reset}
      >
        重置
      </button>
    </div>
  )
}

export default Toolbar
