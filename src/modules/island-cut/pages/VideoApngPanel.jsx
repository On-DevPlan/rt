export default function VideoApngPanel() {
  return (
    <section className="empty-card">
      <h3>视频 → APNG 即将到来</h3>
      <p>
        APNG 支持真彩 + 透明通道，是 GIF 的天然升级版（浏览器原生支持，文件更大）。
      </p>
      <p style={{ marginTop: 10 }}>
        算法骨架可复用本模块的 MP4→GIF 实现；待有真实需求时再切到 APNG 编码（PIL
        直接支持 <code>save(format='PNG', save_all=True)</code>）。
      </p>
    </section>
  )
}