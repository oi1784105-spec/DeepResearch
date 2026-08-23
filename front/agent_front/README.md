# Deep Research 前端

前端使用 Vue 3、TypeScript 和 Vite，负责登录、Provider 配置、模型选择、对话、文件上传、历史会话和语音交互。

## 本地开发

```bash
npm install
npm run dev -- --host 0.0.0.0
```

开发服务器默认使用 5173 端口，并将 /api 和 /health 代理到后端 8000 端口。

## 检查与构建

```bash
npm run type-check
npm run build
```

构建产物位于 dist，生产环境应由 Nginx 或其他静态服务器托管。前后端分离部署时，后端的 CORS_ALLOW_ORIGINS 必须包含实际前端来源。
