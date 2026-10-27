import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// During `npm run dev`, forward API calls to the Python backend (python run.py, port 8000).
// In production the backend serves the built files itself, so no proxy is involved.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
