import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { apiBaseUrlProblem } from './config/apiBaseUrl.js'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    // Falha cedo se a URL do backend gravada no bundle for inválida (ver config/apiBaseUrl.js).
    const problem = apiBaseUrlProblem(loadEnv(mode, process.cwd(), 'VITE_').VITE_API_BASE_URL)
    if (problem) throw new Error(problem)
  }
  return {
    plugins: [react()],
    build: {
      // O maior pedaço é o Three.js do avatar 3D da Mel (~620 kB, ~155 kB gzip), baixado só quando
      // o avatar aparece (import dinâmico em MelAvatar3D); o bundle inicial continua pequeno.
      chunkSizeWarningLimit: 700,
    },
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
  }
})
