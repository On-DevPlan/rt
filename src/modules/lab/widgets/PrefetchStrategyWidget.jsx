const items = [
  'sidebar 链接 hover / focus 时触发对应 page chunk 预加载。',
  'widget 和 page 都使用相同的 cached loader，避免重复请求。',
  'registry 在初始化时同步生成，因此路由可立即可用。'
]

export default function PrefetchStrategyWidget() {
  return (
    <>
      <h3>Prefetch Strategy</h3>
      <div className="list">
        {items.map((item) => (
          <div key={item} className="list-row">
            <span>{item}</span>
          </div>
        ))}
      </div>
    </>
  )
}
