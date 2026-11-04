import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useConversations } from '../../src/hooks/useConversations.js'
import { SESSION, apiError, bodyOf, callsTo, chatReply, jsonResponse, mockApi } from '../helpers.js'

vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test'))

const STORAGE_KEY = 'emporio.conversations.api.v1'

async function renderReady() {
  const hook = renderHook(() => useConversations())
  await waitFor(() => expect(hook.result.current.active.sessionId).toBe('sess-1'))
  return hook
}

function texts(result) {
  return result.current.active.messages.map((message) => [message.role, message.text])
}

describe('useConversations (modo API)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('abre a sessão no backend e mostra a saudação real', async () => {
    mockApi({ 'POST /api/sessions': jsonResponse(SESSION) })
    const { result } = await renderReady()

    expect(result.current.isDemo).toBe(false)
    expect(texts(result)).toEqual([['assistant', 'Olá! Eu sou a Mel.']])
  })

  it('envia a mensagem na sessão aberta, mostra a resposta e persiste no navegador', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': chatReply('Temos violões a partir de R$ 429,90.'),
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('  Quais violões vocês têm?  '))

    expect(bodyOf(callsTo(fetchMock, 'POST /api/chat')[0])).toEqual({
      session_id: 'sess-1',
      message: 'Quais violões vocês têm?',
    })
    expect(texts(result).slice(1)).toEqual([
      ['user', 'Quais violões vocês têm?'],
      ['assistant', 'Temos violões a partir de R$ 429,90.'],
    ])
    expect(result.current.active.title).toBe('Quais violões vocês têm?')
    expect(result.current.isSending).toBe(false)
    expect(result.current.error).toBe('')
    expect(localStorage.getItem(STORAGE_KEY)).toContain('Temos violões a partir de R$ 429,90.')
  })

  it('ignora mensagens vazias', async () => {
    const fetchMock = mockApi({ 'POST /api/sessions': jsonResponse(SESSION) })
    const { result } = await renderReady()

    let sent
    await act(async () => {
      sent = await result.current.sendMessage('   ')
    })

    expect(sent).toBe(false)
    expect(callsTo(fetchMock, 'POST /api/chat')).toHaveLength(0)
  })

  it('mostra erro amigável quando o agente está indisponível e o "Tentar de novo" reenvia', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': [apiError(503, 'agent_unavailable', 'x'), chatReply('Agora sim.')],
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))
    expect(result.current.error).toMatch(/indisponível no momento/)
    expect(result.current.canRetry).toBe(true)

    await act(async () => {
      result.current.retryLast()
    })
    await waitFor(() => expect(result.current.error).toBe(''))

    const chatCalls = callsTo(fetchMock, 'POST /api/chat')
    expect(chatCalls).toHaveLength(2)
    expect(bodyOf(chatCalls[1]).message).toBe('Oi')
    // O reenvio não duplica a mensagem do cliente.
    expect(texts(result).slice(1)).toEqual([
      ['user', 'Oi'],
      ['assistant', 'Agora sim.'],
    ])
  })

  it('não oferece nova tentativa para mensagem inválida (422)', async () => {
    mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': apiError(422, 'invalid_request', 'O campo message é obrigatório.'),
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))

    expect(result.current.error).toBe('O campo message é obrigatório.')
    expect(result.current.canRetry).toBe(false)
  })

  it('conversa no limite de mensagens (429 session_full) mostra o aviso sem nova tentativa', async () => {
    const aviso = 'Esta conversa ficou muito longa. Inicie uma nova conversa para continuar.'
    mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': apiError(429, 'session_full', aviso),
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))

    expect(result.current.error).toBe(aviso)
    expect(result.current.canRetry).toBe(false)
  })

  it('servidor ocupado (503 busy) mostra o aviso e permite tentar de novo', async () => {
    const aviso = 'Estou atendendo muitas conversas agora. Tente novamente em alguns instantes.'
    mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': apiError(503, 'busy', aviso),
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))

    expect(result.current.error).toBe(aviso)
    expect(result.current.canRetry).toBe(true)
  })

  it('quando a sessão expirou (404), avisa e reenvia uma vez numa sessão nova', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': [apiError(404, 'session_not_found', 'x'), chatReply('Resposta na sessão nova.', 'sess-2')],
    })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))

    const chatCalls = callsTo(fetchMock, 'POST /api/chat')
    expect(chatCalls.map((call) => bodyOf(call).session_id)).toEqual(['sess-1', null])
    expect(result.current.active.sessionId).toBe('sess-2')
    expect(texts(result).map(([role]) => role)).toEqual(['assistant', 'user', 'notice', 'assistant'])
    expect(result.current.error).toBe('')
  })

  it('espera e tenta de novo sozinho quando a sessão está ocupada (409)', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': [apiError(409, 'session_busy', 'x'), chatReply('Pronto.')],
    })
    const { result } = await renderReady()
    vi.useFakeTimers()

    let sending
    act(() => {
      sending = result.current.sendMessage('Oi')
    })
    await act(() => vi.advanceTimersByTimeAsync(2000))
    await act(() => sending)

    expect(callsTo(fetchMock, 'POST /api/chat')).toHaveLength(2)
    expect(texts(result).at(-1)).toEqual(['assistant', 'Pronto.'])
    expect(result.current.error).toBe('')
  })

  it('trata resposta vazia do assistente como erro', async () => {
    mockApi({ 'POST /api/sessions': jsonResponse(SESSION), 'POST /api/chat': chatReply('   ') })
    const { result } = await renderReady()

    await act(() => result.current.sendMessage('Oi'))

    expect(result.current.error).toMatch(/não retornou conteúdo/)
    expect(texts(result).at(-1)).toEqual(['user', 'Oi'])
  })

  it('avisa quando a saudação falha e permite tentar abrir a sessão de novo', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': [apiError(503, 'agent_unavailable', 'x'), jsonResponse(SESSION)],
    })
    const { result } = renderHook(() => useConversations())

    await waitFor(() => expect(result.current.error).toMatch(/Não foi possível iniciar o atendimento/))

    await act(async () => {
      result.current.retryLast()
    })
    await waitFor(() => expect(result.current.active.sessionId).toBe('sess-1'))
    expect(callsTo(fetchMock, 'POST /api/sessions')).toHaveLength(2)
  })

  it('nova conversa abre outra sessão sem perder a anterior; a busca filtra pelo conteúdo', async () => {
    mockApi({
      'POST /api/sessions': [jsonResponse(SESSION), jsonResponse({ ...SESSION, session_id: 'sess-2' })],
      'POST /api/chat': chatReply('Sobre violões: temos vários.'),
    })
    const { result } = await renderReady()
    await act(() => result.current.sendMessage('violões'))
    const firstId = result.current.active.id

    act(() => {
      result.current.startConversation()
    })
    await waitFor(() => expect(result.current.active.sessionId).toBe('sess-2'))
    expect(result.current.active.id).not.toBe(firstId)
    expect(result.current.conversations).toHaveLength(2)

    act(() => {
      result.current.setQuery('VIOLÕES')
    })
    expect(result.current.conversations.map((item) => item.id)).toEqual([firstId])
  })

  it('cada nova conversa recebe uma animação da Mel diferente da conversa ativa, sem chamada extra à API', async () => {
    const fetchMock = mockApi({
      'POST /api/sessions': [
        jsonResponse(SESSION),
        jsonResponse({ ...SESSION, session_id: 'sess-2' }),
        jsonResponse({ ...SESSION, session_id: 'sess-3' }),
        jsonResponse({ ...SESSION, session_id: 'sess-4' }),
      ],
    })
    const { result } = await renderReady()
    const ids = ['dancing', 'ukulele', 'singing', 'headphones', 'surprise']
    let previous = result.current.active.animation
    expect(ids).toContain(previous)

    for (const session of ['sess-2', 'sess-3', 'sess-4']) {
      act(() => {
        result.current.startConversation()
      })
      await waitFor(() => expect(result.current.active.sessionId).toBe(session))
      expect(ids).toContain(result.current.active.animation)
      expect(result.current.active.animation).not.toBe(previous)
      previous = result.current.active.animation
    }
    // Só a criação das sessões vai à API: a escolha da animação é local.
    expect(callsTo(fetchMock, 'POST /api/sessions')).toHaveLength(4)
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)).conversations.every((item) => item.animation)).toBe(true)
  })

  it('restaura as conversas salvas no navegador sem abrir nova sessão', async () => {
    const saved = {
      activeId: 'c-1',
      conversations: [
        {
          id: 'c-1',
          title: 'Conversa salva',
          sessionId: 'sess-old',
          updatedAt: '2026-03-25T13:00:00Z',
          messages: [{ id: 'm1', role: 'user', text: 'Mensagem antiga', createdAt: '2026-03-25T13:00:00Z' }],
        },
      ],
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved))
    const fetchMock = mockApi({})

    const { result } = renderHook(() => useConversations())

    expect(result.current.active.title).toBe('Conversa salva')
    expect(texts(result)).toEqual([['user', 'Mensagem antiga']])
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
