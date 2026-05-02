import { ReactFlowProvider } from '@xyflow/react'
import { Flow, Toolbar, PropertiesPanel, GraphInfo } from '../components'
import useWorkflowStore from '../store'
import styles from './FlowBuilderPage.module.css'

function FlowBuilderPageContent() {
  const { nodes, edges } = useWorkflowStore()

  return (
    <div className="page-stack">
      <section className={styles.shell}>
        <header className={styles.header}>
          <div>
            <h2>Flow Builder</h2>
            <p>可视化工作流编辑器 - 支持多种节点类型和图论分析</p>
          </div>
        </header>

        <div className={styles.layout}>
          <aside className={styles.sidebar}>
            <Toolbar />
            <GraphInfo />
          </aside>

          <main className={styles.canvas}>
            <Flow />
          </main>

          <aside className={styles.properties}>
            <PropertiesPanel />
          </aside>
        </div>

        <footer className={styles.footer}>
          <span>节点: {nodes.length}</span>
          <span>|</span>
          <span>连线: {edges.length}</span>
        </footer>
      </section>
    </div>
  )
}

export default function FlowBuilderPage() {
  return (
    <ReactFlowProvider>
      <FlowBuilderPageContent />
    </ReactFlowProvider>
  )
}
