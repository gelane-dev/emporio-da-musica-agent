/**
 * Validação de VITE_API_BASE_URL no build (vite.config.js).
 *
 * O Vite grava a variável no bundle durante o build: um valor errado (por exemplo um placeholder
 * como "https://SUA-URL-DO-RENDER") gera um site que abre, mas em que todo chamado à API falha
 * como erro de rede. Melhor o build falhar com uma mensagem clara do que publicar isso.
 * Vazio continua válido: é o modo demonstrativo.
 */
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

export function apiBaseUrlProblem(value) {
  const raw = (value ?? '').trim()
  if (!raw) return null
  let url
  try {
    url = new URL(raw)
  } catch {
    return `VITE_API_BASE_URL não é uma URL válida: "${raw}".`
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    return `VITE_API_BASE_URL precisa começar com https:// (ou http:// em ambiente local): "${raw}".`
  }
  const host = url.hostname.toLowerCase()
  if (!LOCAL_HOSTS.has(host) && !host.includes('.')) {
    return `VITE_API_BASE_URL parece um placeholder, sem domínio real: "${raw}". Use a URL pública do backend (ex.: https://seu-servico.onrender.com).`
  }
  if (url.pathname !== '/' || url.search || url.hash) {
    return `VITE_API_BASE_URL deve ser só a origem do backend, sem caminho (as rotas /api são acrescentadas pelo frontend): "${raw}".`
  }
  return null
}
