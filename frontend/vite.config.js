import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      // FastAPI backend — the UI falls back to bundled mock data when this is down
      '/api': 'http://localhost:8000'
    }
  }
});
