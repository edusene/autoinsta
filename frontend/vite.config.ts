import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento, /api, /webhooks e /health vão para o Flask local.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/webhooks': 'http://127.0.0.1:5000',
      '/health': 'http://127.0.0.1:5000',
    },
  },
})
