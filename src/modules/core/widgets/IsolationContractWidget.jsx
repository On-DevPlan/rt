const contracts = [
  '一个模块一个 module.meta.js，避免路由、导航、标签散落多个文件。',
  '页面入口固定放在 pages/，挂载型组件固定放在 widgets/。',
  'registry 只依赖 metadata，不依赖页面组件执行副作用。',
  '任何模块都可以独立新增、迁移或删除，不需要动中心化路由表。'
]

export default function IsolationContractWidget() {
  return (
    <>
      <h3>Isolation Contract</h3>
      <div className="list">
        {contracts.map((item) => (
          <div key={item} className="list-row">
            <span>{item}</span>
          </div>
        ))}
      </div>
    </>
  )
}
