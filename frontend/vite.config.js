import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig, loadEnv } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, repositoryRoot, '');
  const mirofishEnv = loadEnv(mode, path.join(repositoryRoot, 'mirofish'), '');
  const apiTarget =
    process.env.MIROFISH_API_URL ||
    rootEnv.MIROFISH_API_URL ||
    mirofishEnv.MIROFISH_API_URL ||
    'http://127.0.0.1:5001';
  return {
    plugins: [svelte()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true
        }
      }
    }
  };
});
