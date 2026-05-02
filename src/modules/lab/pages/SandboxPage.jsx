const treeSnippet = `src/modules/orders/
  module.meta.js
  pages/
    DashboardPage.jsx
    DetailPage.jsx
  widgets/
    OrdersHealthWidget.jsx
    OrdersFiltersWidget.jsx`

export default function SandboxPage() {
  return (
    <div className="page-stack">
      <article className="tip-card">
        <h3>接入步骤</h3>
        <p>
          新建一个模块目录，放入 `module.meta.js`、`pages/`、`widgets/`。
          页面一旦声明 `route` 和 `entry`，框架就会自动把它纳入路由、导航和注册表。
        </p>
      </article>

      <section className="module-grid">
        <div className="code-panel">
          <h3>推荐目录</h3>
          <pre>{treeSnippet}</pre>
        </div>
        <div className="tip-card">
          <h3>性能策略</h3>
          <p>
            metadata 小而稳定，适合同步导入；真正重的业务页和图形组件继续切 chunk。
            如果将来模块继续增加，启动性能仍然主要受 metadata 数量影响，而不是页面体积影响。
          </p>
        </div>
      </section>

      <section className="code-panel">
        <h3>为什么比 ve 的扫描方式更适合 React</h3>
        <pre>{`- React 侧更自然的做法是把 route element 和 lazy loader 直接在 registry 中建好。
- 不需要先 mount 应用，再额外等待一次 route setup。
- Suspense 原生处理页面与 widget 的异步边界。`}</pre>
      </section>
    </div>
  )
}
