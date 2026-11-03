import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{js,jsx}'],
    setupFiles: ['./tests/setup.js'],
    // Os testes nunca chamam o backend real: cada teste define o modo (demo ou API) e mocka o fetch.
    env: { VITE_API_BASE_URL: '' },
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
})
