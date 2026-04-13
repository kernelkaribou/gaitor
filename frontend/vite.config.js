import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [
    tailwindcss(),
    svelte(),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8487',
      '/health': 'http://localhost:8487',
      '/ws': {
        target: 'ws://localhost:8487',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
