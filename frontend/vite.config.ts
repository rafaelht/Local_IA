import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],

  server: {
    host: true,
    port: 5173,

    // Permite acceder desde cualquier hostname de tu red
    allowedHosts: true,

    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },

      '/litert-api': {
        target: 'http://10.0.0.84:9379',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/litert-api/, ''),
      },

      '/ollama-api': {
        target: 'http://ollama:11434',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ollama-api/, ''),
      },
    },
  },

  preview: {
    host: true,
    port: 4173,
    allowedHosts: true,
  },

  build: {
    target: 'es2020',
    sourcemap: false,
    cssCodeSplit: true,

    chunkSizeWarningLimit: 1000,

    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom'],
          router: ['react-router-dom'],
          query: ['@tanstack/react-query'],
          state: ['zustand'],
        },
      },
    },
  },
})