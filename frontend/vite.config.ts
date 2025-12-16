import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  build: {
    // Raise warning limit - MUI core is ~414kB (unavoidable for full MUI usage)
    chunkSizeWarningLimit: 450,

    // Target modern browsers for smaller output
    target: 'es2020',

    // No source maps in production (smaller Docker images)
    sourcemap: false,

    // Use esbuild (bundled with Vite, faster than terser)
    minify: 'esbuild',

    rollupOptions: {
      output: {
        // Manual chunk splitting for optimal caching and smaller bundles
        manualChunks: {
          // React core - changes rarely
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],

          // MUI core - large but stable
          'vendor-mui-core': [
            '@mui/material',
            '@mui/system',
            '@emotion/react',
            '@emotion/styled',
          ],

          // MUI icons - tree-shake friendly, separate chunk
          'vendor-mui-icons': ['@mui/icons-material'],

          // Data grid - only used in admin, heavy
          'vendor-datagrid': ['@mui/x-data-grid'],

          // Charts - only used in admin dashboard
          'vendor-recharts': ['recharts'],

          // Utilities
          'vendor-utils': ['axios', 'uuid'],
        },
      },
    },
  },

  // Drop console/debugger in production builds
  esbuild: {
    drop: ['console', 'debugger'],
  },

  // Pre-bundle heavy deps for faster dev server
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@mui/material',
      '@mui/icons-material',
      'axios',
    ],
  },
})
