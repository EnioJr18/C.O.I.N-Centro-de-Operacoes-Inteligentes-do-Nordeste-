import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'COIN_')
  const target = env.COIN_BACKEND_ORIGIN || 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173, strictPort: true,
      proxy: {
        '/api/': { target, changeOrigin: true },
        '/ws/': { target, ws: true, changeOrigin: true, rewriteWsOrigin: false },
      },
    },
    test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
  }
})
