import { describe, expect, it, vi } from 'vitest'
import { checkHealth, createSession, isDemoMode, sendChatMessage } from '../../src/services/chatService.js'
import { HEALTH_OK, bodyOf, callsTo, jsonResponse, mockApi } from '../helpers.js'

vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test'))

describe('chatService no modo API', () => {
  it('não está em modo demonstrativo', () => {
    expect(isDemoMode()).toBe(false)
  })

  it('createSession abre a sessão e devolve a saudação real', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': jsonResponse({ session_id: 's-9', greeting: 'Oi, sou a Mel', created_at: '2026-03-25T13:00:00Z' }),
    })

    await expect(createSession()).resolves.toEqual({
      sessionId: 's-9',
      greeting: 'Oi, sou a Mel',
      createdAt: '2026-03-25T13:00:00Z',
    })
    expect(callsTo(fetchMock, 'POST /api/sessions')).toHaveLength(1)
  })

  it('sendChatMessage envia session_id e message e normaliza a resposta', async () => {
    const fetchMock = mockApi({
      'POST /api/chat': jsonResponse({
        session_id: 's-9',
        reply: 'Temos sim.',
        stop: 'end_turn',
        tool_calls: [{ name: 'buscar_produtos' }],
      }),
    })

    const reply = await sendChatMessage({ sessionId: 's-9', conversationId: 'c1', message: 'Tem violão?' })

    expect(bodyOf(fetchMock.mock.calls[0])).toEqual({ session_id: 's-9', message: 'Tem violão?' })
    expect(reply).toEqual({
      text: 'Temos sim.',
      products: [],
      sessionId: 's-9',
      stop: 'end_turn',
      toolCalls: [{ name: 'buscar_produtos' }],
    })
  })

  it('sendChatMessage sem sessão envia session_id null e tolera campos ausentes', async () => {
    const fetchMock = mockApi({ 'POST /api/chat': jsonResponse({}) })

    const reply = await sendChatMessage({ message: 'oi' })

    expect(bodyOf(fetchMock.mock.calls[0])).toEqual({ session_id: null, message: 'oi' })
    expect(reply).toEqual({ text: '', products: [], sessionId: null, stop: null, toolCalls: [] })
  })

  it('checkHealth consulta GET /api/health', async () => {
    mockApi({ 'GET /api/health': jsonResponse(HEALTH_OK) })
    await expect(checkHealth()).resolves.toEqual(HEALTH_OK)
  })
})
