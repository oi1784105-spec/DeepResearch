import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import { installDemoNetwork } from './demo'

// 演示构建必须在挂载前安装网络垫片：
// 组件挂载时就会立即请求 /auth/me、/providers、/research/conversations。
installDemoNetwork()

createApp(App).mount('#app')
