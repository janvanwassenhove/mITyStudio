import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Minimal declaration so vue-tsc doesn't require @types/node just for this.
declare const process: { env: Record<string, string | undefined> }

// Backend port is overridable (MITY_API_PORT) so the dev UI can point at a
// separate backend instance without editing config.
const apiPort = process.env.MITY_API_PORT || '8000'
// Stamped by CI (MITY_APP_VERSION) so the About box can compare the UI build
// against the backend — a mismatch means a half-applied update.
const appVersion = process.env.MITY_APP_VERSION || 'dev'

export default defineConfig({
  plugins: [vue()],
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
  },
  server: {
    // PORT lets a launcher assign a free port; default stays 5173
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true },
    },
  },
})
