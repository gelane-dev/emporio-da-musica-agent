const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

/** Tempo máximo de espera por resposta. O agente (LLM + ferramentas) pode demorar. */
export const REQUEST_TIMEOUT_MS = 90_000

const FALLBACK_MESSAGE = 'O atendimento está temporariamente indisponível. Tente novamente em instantes.'

export function getApiBaseUrl() {
  return String(BASE_URL).trim().replace(/\/$/, '')
}

export function hasRemoteApi() {
  return Boolean(getApiBaseUrl())
}

/**
 * Erro de chamada HTTP com o status e o código do envelope `{error, message}`.
 * `status` é 0 quando não houve resposta (rede ou timeout).
 */
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'unknown' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/**
 * Cliente HTTP único. Componentes não devem chamar fetch nem conhecer paths.
 */
export async function request(path, options = {}) {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchOptions } = options
  const url = `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`
  const headers = {
    Accept: 'application/json',
    ...(fetchOptions.body ? { 'Content-Type': 'application/json' } : {}),
    ...fetchOptions.headers,
  }

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  let response
  let payload
  try {
    response = await fetch(url, { ...fetchOptions, headers, signal: controller.signal })
    payload = await readBody(response)
  } catch {
    if (timedOut) {
      throw new ApiError('O atendimento demorou demais para responder. Tente de novo em instantes.', {
        code: 'timeout',
      })
    }
    throw new ApiError('Não foi possível conectar ao atendimento. Verifique sua conexão e tente de novo.', {
      code: 'network',
    })
  } finally {
    clearTimeout(timer)
  }

  if (!response.ok) {
    const message = (payload && typeof payload.message === 'string' && payload.message) || FALLBACK_MESSAGE
    const code = (payload && typeof payload.error === 'string' && payload.error) || 'http_error'
    throw new ApiError(message, { status: response.status, code })
  }
  return payload
}

async function readBody(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { raw: text }
  }
}
