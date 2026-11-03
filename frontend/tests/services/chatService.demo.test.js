import { afterEach, describe, expect, it, vi } from 'vitest'
import { WELCOME_TEXT } from '../../src/data/demo.js'
import { checkHealth, createSession, isDemoMode, sendChatMessage } from '../../src/services/chatService.js'

describe('chatService no modo demonstrativo (sem VITE_API_BASE_URL)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('não faz nenhuma chamada de rede', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()

    expect(isDemoMode()).toBe(true)
    await expect(createSession()).resolves.toMatchObject({ sessionId: null, greeting: WELCOME_TEXT })
    await expect(checkHealth()).resolves.toEqual({ status: 'demo', agent_ready: false })

    const pending = sendChatMessage({ conversationId: 'c1', message: 'Quero um baixo' })
    await vi.advanceTimersByTimeAsync(2000)
    const reply = await pending

    expect(reply.stop).toBe('demo')
    expect(reply.text).toMatch(/Jazz Bass/)
    expect(reply.products.length).toBeGreaterThan(0)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
