import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useBackendHealth } from '../../src/hooks/useBackendHealth.js'
import { HEALTH_OK, jsonResponse, mockApi } from '../helpers.js'

vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test'))

describe('useBackendHealth (modo API)', () => {
  it('começa em "checking" e passa a "online" quando o agente está pronto', async () => {
    mockApi({ 'GET /api/health': jsonResponse(HEALTH_OK) })
    const { result } = renderHook(() => useBackendHealth())

    expect(result.current.status).toBe('checking')
    await waitFor(() => expect(result.current).toEqual({ status: 'online', detail: null }))
  })

  it('fica "degraded" com o detalhe quando o servidor responde sem agente', async () => {
    mockApi({
      'GET /api/health': jsonResponse({ status: 'degraded', agent_ready: false, detail: 'Chave ausente.' }),
    })
    const { result } = renderHook(() => useBackendHealth())

    await waitFor(() => expect(result.current).toEqual({ status: 'degraded', detail: 'Chave ausente.' }))
  })

  it('fica "offline" quando o servidor não responde', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    const { result } = renderHook(() => useBackendHealth())

    await waitFor(() => expect(result.current.status).toBe('offline'))
  })
})
