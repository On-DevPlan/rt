export default function RouteMapWidget({ registry }) {
  return (
    <>
      <h3>Route Map</h3>
      <div className="list">
        {registry.pages.map((page) => (
          <div key={page.id} className="list-row">
            <span>{page.title}</span>
            <code>{page.route}</code>
          </div>
        ))}
      </div>
    </>
  )
}
