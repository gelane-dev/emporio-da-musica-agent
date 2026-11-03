import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getApiBaseUrl, hasRemoteApi, request } from '../../src/services/http.js'
import { jsonResponse } from '../helpers.js'

vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test/'))

async function captureError(promise) {
  try {
    await promise
  } catch (err) {
    return err
  }
  throw new Error('a promessa deveria falhar')
}

describe('request()', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('normaliza a URL base (sem barra final) e liga o modo API', () => {
    expect(getApiBaseUrl()).toBe('http://api.test')
    expect(hasRemoteApi()).toBe(true)
  })

  it('monta a URL, envia JSON e devolve o corpo decodificado', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ reply: 'oi' }))
    vi.stubGlobal('fetch', fetchMock)

    const payload = await request('/api/chat', { method: 'POST', body: '{"message":"oi"}' })

    expect(payload).toEqual({ reply: 'oi' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/api/chat')
    expect(init.headers).toMatchObject({ Accept: 'application/json', 'Content-Type': 'application/json' })
  })

  it('não declara Content-Type em requisições sem corpo e aceita caminho sem barra inicial', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchMock)

    await request('api/health', { method: 'GET' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/api/health')
    expect(init.headers).not.toHaveProperty('Content-Type')
  })

  it('devolve null quando a resposta não tem corpo', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(undefined, 204)))
    await expect(request('/api/x')).resolves.toBeNull()
  })

  it('converte o envelope de erro {error, message} em ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ error: 'session_busy', message: 'Aguarde.' }, 409)))

    const err = await captureError(request('/api/chat', { method: 'POST', body: '{}' }))

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 409, code: 'session_busy', message: 'Aguarde.' })
  })

  it('usa mensagem genérica quando o erro não segue o envelope', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 502, text: async () => '<html>Bad gateway</html>' })))

    const err = await captureError(request('/api/chat'))

    expect(err).toMatchObject({ status: 502, code: 'http_error' })
    expect(err.message).toMatch(/temporariamente indisponível/)
  })

  it('identifica falha de rede (sem resposta)', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))

    const err = await captureError(request('/api/health'))

    expect(err).toMatchObject({ status: 0, code: 'network' })
    expect(err.message).toMatch(/Não foi possível conectar/)
  })

  it('aborta a requisição e informa timeout quando o servidor demora demais', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url, init) =>
          new Promise((_resolve, reject) => {
            init.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
          }),
      ),
    )

    const pending = captureError(request('/api/chat', { timeoutMs: 1000 }))
    await vi.advanceTimersByTimeAsync(1000)
    const err = await pending

    expect(err).toMatchObject({ status: 0, code: 'timeout' })
    expect(err.message).toMatch(/demorou demais/)
  })
})
