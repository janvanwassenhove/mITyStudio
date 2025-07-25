import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/ai': 'http://localhost:5000',
      '/api/voice': 'http://localhost:5000',
    },
  },
})
