import { vi } from 'vitest'

/**
 * URL da API nos testes do modo API. Os arquivos desse modo ligam a variável antes das importações:
 *   vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test'))
 * (os módulos leem `VITE_API_BASE_URL` uma única vez, ao serem importados).
 */
export const API_URL = 'http://api.test'

/** Resposta HTTP mínima no formato usado por `request()` (lê o corpo com `text()`). */
export function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === undefined ? '' : JSON.stringify(body)),
  }
}

/**
 * Substitui o `fetch` global. `routes` mapeia "MÉTODO /caminho" para uma resposta, uma função
 * `(init) => resposta` ou um array delas (consumidas em ordem; a última se repete).
 * Rota não mapeada falha o teste: nenhuma chamada sai para a rede.
 */
export function mockApi(routes) {
  const queues = new Map(
    Object.entries(routes).map(([key, value]) => [key, Array.isArray(value) ? [...value] : [value]]),
  )
  const fetchMock = vi.fn(async (url, init = {}) => {
    const key = `${init.method ?? 'GET'} ${String(url).replace(API_URL, '')}`
    const queue = queues.get(key)
    if (!queue) throw new Error(`Rota não mockada: ${key}`)
    const next = queue.length > 1 ? queue.shift() : queue[0]
    return typeof next === 'function' ? next(init) : next
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Chamadas feitas a uma rota ("MÉTODO /caminho"). */
export function callsTo(fetchMock, key) {
  return fetchMock.mock.calls.filter(([url, init = {}]) => `${init.method ?? 'GET'} ${String(url).replace(API_URL, '')}` === key)
}

export function bodyOf(call) {
  return JSON.parse(call[1].body)
}

export const SESSION = { session_id: 'sess-1', greeting: 'Olá! Eu sou a Mel.', created_at: '2026-03-25T13:00:00Z' }
export const HEALTH_OK = { status: 'ok', agent_ready: true, provider: 'groq', model: 'openai/gpt-oss-120b', detail: null }

export function chatReply(reply, sessionId = 'sess-1') {
  return jsonResponse({ session_id: sessionId, reply, stop: 'end_turn', tool_calls: [] })
}

export function apiError(status, error, message) {
  return jsonResponse({ error, message }, status)
}
