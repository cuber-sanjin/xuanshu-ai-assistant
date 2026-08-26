import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端地址可通过环境变量覆盖（端口冲突时换端口，无需改代码）：
//   VITE_API_TARGET=http://127.0.0.1:8001 npm run dev
const apiTarget = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 开发期代理：前端所有 /api 请求转发到 FastAPI 后端
    // 作用：1) 免去 CORS 配置  2) 前端代码写相对路径 /api，生产环境由 nginx 做同样代理
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
