import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    // GitHub Pages 部署在 /<repo>/ 子路径下，需要显式指定 base；
    // 本地开发与常规服务器部署保持默认的 '/'。
    base: env.VITE_BASE || '/',
    plugins: [
      vue(),
      // devtools 只在开发服务器启用：它属于调试工具，不应进入生产产物。
      ...(command === 'serve' ? [vueDevTools()] : []),
    ],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      },
    },
  }
})
