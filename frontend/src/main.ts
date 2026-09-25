import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useSessionStore } from './stores/session'
import './styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 先拉取当班人员目录与当前班次，再挂载界面，避免身份未就绪时误判权限。
const session = useSessionStore()
session
  .bootstrap()
  .catch(() => {
    // 后端暂不可用时界面仍可加载，理货页会按只读展示并提示接口失败。
  })
  .finally(() => {
    app.mount('#app')
  })
