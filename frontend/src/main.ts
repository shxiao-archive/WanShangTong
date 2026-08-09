import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/600.css'
import '@fontsource/noto-sans-sc/700.css'
import '@/assets/main.css'
import App from './App.vue'
import router from './router'

createApp(App).use(ElementPlus).use(router).mount('#app')
