import { WELCOME_TEXT } from '../data/demo.js'
import { demoRespond } from '../data/demoChat.js'
import { hasRemoteApi, request } from './http.js'

/**
 * Camada de atendimento.
 *
 * Sem VITE_API_BASE_URL: modo demonstrativo (respostas fictícias de src/data, sem agente).
 * Com VITE_API_BASE_URL: API FastAPI do backend (prefixo /api — só aqui, nunca nos componentes).
 */
export function isDemoMode() {
  return !hasRemoteApi()
}

/** Cria uma sessão no backend e devolve a saudação real da Mel. */
export async function createSession() {
  if (isDemoMode()) {
    return { sessionId: null, greeting: WELCOME_TEXT, createdAt: new Date().toISOString() }
  }
  const payload = await request('/api/sessions', { method: 'POST' })
  return {
    sessionId: payload?.session_id ?? null,
    greeting: typeof payload?.greeting === 'string' ? payload.greeting : '',
    createdAt: payload?.created_at ?? new Date().toISOString(),
  }
}

/**
 * Envia uma mensagem. Retorno normalizado:
 * `{ text, products, sessionId, stop, toolCalls }`.
 * No modo API não há produtos estruturados: a resposta é só texto.
 */
export async function sendChatMessage({ sessionId, conversationId, message, history }) {
  if (isDemoMode()) {
    const reply = await demoRespond({ conversationId, message, history })
    return { ...reply, sessionId: null, stop: 'demo', toolCalls: [] }
  }

  const payload = await request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId ?? null, message }),
  })

  return {
    text: typeof payload?.reply === 'string' ? payload.reply : '',
    products: [],
    sessionId: payload?.session_id ?? null,
    stop: payload?.stop ?? null,
    toolCalls: Array.isArray(payload?.tool_calls) ? payload.tool_calls : [],
  }
}

/** Estado do backend: `{ status, agent_ready, provider, model, detail }`. */
export async function checkHealth() {
  if (isDemoMode()) return { status: 'demo', agent_ready: false }
  return request('/api/health', { method: 'GET', timeoutMs: 10_000 })
}
