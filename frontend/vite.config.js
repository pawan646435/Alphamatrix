import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Warn on chunks larger than 500kb
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // Manual chunk splitting to keep initial bundle minimal
        manualChunks(id) {
          // Firebase into its own chunk — large library rarely changes
          if (id.includes('node_modules/firebase')) {
            return 'firebase';
          }
          // Recharts + d3 deps into a chart chunk
          if (
            id.includes('node_modules/recharts') ||
            id.includes('node_modules/d3-') ||
            id.includes('node_modules/victory-vendor')
          ) {
            return 'charts';
          }
          // React core — always keep in its own small chunk
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/react-router-dom')
          ) {
            return 'react-vendor';
          }
          // Lucide icons — large icon set, separate chunk
          if (id.includes('node_modules/lucide-react')) {
            return 'icons';
          }
          // Axios — small but shared utility
          if (id.includes('node_modules/axios')) {
            return 'http';
          }
        },
      },
    },
  },
  // Optimize dep pre-bundling
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'axios'],
  },
})
