/**
 * Cấu hình Vite (dev server + build SPA).
 * Proxy `/api` → backend (`API_PROXY_TARGET` hoặc `127.0.0.1:8000`) để tránh CORS khi dev local.
 */
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

// In Docker, use service hostname `backend` (see docker-compose). On host dev, use 127.0.0.1.
const apiProxyTarget =
  process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    sourcemap: false,
    // Skips gzip size step — noticeably faster on small EC2 instances
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1200,
  },
  server: {
    port: 3000,
    strictPort: true,
    host: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});

