export default function RegistryStatsWidget({ registry }) {
  return (
    <>
      <h3>Registry Stats</h3>
      <div className="list">
        <div className="list-row">
          <span>Modules</span>
          <code>{registry.stats.moduleCount}</code>
        </div>
        <div className="list-row">
          <span>Pages</span>
          <code>{registry.stats.pageCount}</code>
        </div>
        <div className="list-row">
          <span>Widgets</span>
          <code>{registry.stats.widgetCount}</code>
        </div>
        <div className="list-row">
          <span>Routes</span>
          <code>{registry.stats.routeCount}</code>
        </div>
      </div>
    </>
  )
}
