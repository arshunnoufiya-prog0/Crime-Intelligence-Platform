import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy (build plumbing, outside frontend/src — §0.8 scoping note):
// the live components call /api/* which belongs to Django :8000 in dev.
// In prod, nginx serves the frontend and proxies /api/ to backend:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
