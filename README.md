# RT

一个偏框架形态的 React 示例项目，目标不是堆页面，而是把“发现、注册、路由、元数据、隔离”收拢成一套稳定约定。

## 核心思路

- `src/modules/**/module.meta.js` 负责集中定义模块、页面、组件元数据。
- 发现阶段只 `eager` 导入元数据文件，不在启动时逐个异步探测页面组件。
- 页面和组件通过 `import.meta.glob` 延迟加载，减少首屏扫描和初始执行成本。
- 每个模块自带 `pages/`、`widgets/`，天然隔离，注册时自动进入统一 registry。

## 开发

```bash
npm install
npm run dev
```

开发端口固定为 `81`。

## 目录约定

```text
src/
  app/
  framework/
  modules/
    some-module/
      module.meta.js
      pages/
      widgets/
```

## 部署

- Docker 镜像使用多阶段构建。
- Nginx 对外提供 SPA 路由回退与 `/health` 健康检查。
- GitHub Actions 工作流模仿参考项目 `ve` 的 Docker 打包 + SCP + SSH 发布流程，外部映射端口为 `81`。
