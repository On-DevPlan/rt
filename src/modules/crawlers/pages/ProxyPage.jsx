import { Link } from 'react-router-dom'
import EndpointCard from '../components/EndpointCard.jsx'
import { proxyEndpoints } from '../specs/proxy.js'
import styles from './crawlerPage.module.css'

export default function ProxyPage() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <Link to="/crawlers" className={styles.backlink}>
          ← 返回 Crawler Cookbook
        </Link>
        <h1 className={styles.title}>Proxy 边车（mihomo）</h1>
        <p className={styles.lede}>
          容器内 mihomo（Clash.Meta 内核）边车：填机场的 Clash 订阅 URL，按模块白名单把后端出站
          请求导向代理（被墙的文档站走代理，国内 API 直连）。注意这是<strong>服务端出站代理</strong>，
          不是浏览器代理；订阅 URL 是凭据，仅保存在服务器本地数据卷。
        </p>
      </header>

      <div className={styles.cards}>
        {proxyEndpoints.map((spec) => (
          <EndpointCard key={spec.id} spec={spec} />
        ))}
      </div>
    </div>
  )
}
