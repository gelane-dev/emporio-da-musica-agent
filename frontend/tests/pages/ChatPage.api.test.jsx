import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ChatPage from '../../src/pages/ChatPage.jsx'
import { HEALTH_OK, SESSION, apiError, bodyOf, callsTo, jsonResponse, mockApi } from '../helpers.js'

vi.hoisted(() => vi.stubEnv('VITE_API_BASE_URL', 'http://api.test'))

/** Texto dentro de um balão da conversa (a mesma frase também aparece na prévia da barra lateral). */
const BUBBLE = { selector: '.msg__bubble p' }

function findMessage(text) {
  return screen.findByText(text, BUBBLE)
}

/** Resposta do chat que só chega quando o teste chamar `release()`. */
function deferredReply(reply) {
  let release
  const gate = new Promise((resolve) => {
    release = resolve
  })
  const handler = async () => {
    await gate
    return jsonResponse({ session_id: 'sess-1', reply, stop: 'end_turn', tool_calls: [] })
  }
  return { handler, release: () => release() }
}

describe('ChatPage integrada à API (fetch mockado)', () => {
  it('fluxo completo: saudação, envio, indicador de digitação e resposta da Mel', async () => {
    const reply = deferredReply('O Takamine GD20 custa R$ 2.199,00.')
    const fetchMock = mockApi({
      'GET /api/health': jsonResponse(HEALTH_OK),
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': reply.handler,
    })
    render(<ChatPage />)

    expect(await findMessage('Olá! Eu sou a Mel.')).toBeInTheDocument()
    expect((await screen.findAllByText('Online')).length).toBeGreaterThan(0)

    const input = screen.getByPlaceholderText('Digite sua mensagem...')
    await userEvent.type(input, 'Quanto custa o Takamine GD20?{Enter}')

    expect(screen.getByText('Quanto custa o Takamine GD20?', BUBBLE)).toBeInTheDocument()
    expect(screen.getByLabelText('Assistente está respondendo')).toBeInTheDocument()
    expect(input).toBeDisabled()

    reply.release()

    expect(await findMessage('O Takamine GD20 custa R$ 2.199,00.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Assistente está respondendo')).not.toBeInTheDocument()
    expect(input).toBeEnabled()
    expect(bodyOf(callsTo(fetchMock, 'POST /api/chat')[0])).toEqual({
      session_id: 'sess-1',
      message: 'Quanto custa o Takamine GD20?',
    })
  })

  it('erro da API aparece na conversa e "Tentar de novo" recupera', async () => {
    mockApi({
      'GET /api/health': jsonResponse(HEALTH_OK),
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': [
        apiError(500, 'internal_error', 'Ocorreu um erro inesperado. Tente novamente em instantes.'),
        jsonResponse({ session_id: 'sess-1', reply: 'Resposta após nova tentativa.', stop: 'end_turn', tool_calls: [] }),
      ],
    })
    render(<ChatPage />)
    await findMessage('Olá! Eu sou a Mel.')

    await userEvent.type(screen.getByPlaceholderText('Digite sua mensagem...'), 'Oi{Enter}')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Ocorreu um erro inesperado.')
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar de novo' }))

    expect(await findMessage('Resposta após nova tentativa.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getAllByText('Oi', BUBBLE)).toHaveLength(1)
  })

  it('sugestão envia a pergunta pronta', async () => {
    const fetchMock = mockApi({
      'GET /api/health': jsonResponse(HEALTH_OK),
      'POST /api/sessions': jsonResponse(SESSION),
      'POST /api/chat': jsonResponse({ session_id: 'sess-1', reply: 'Aceitamos PIX e cartão.', stop: 'end_turn', tool_calls: [] }),
    })
    render(<ChatPage />)
    await findMessage('Olá! Eu sou a Mel.')

    await userEvent.click(screen.getByRole('button', { name: 'Como funciona o pagamento?' }))

    expect(await findMessage('Aceitamos PIX e cartão.')).toBeInTheDocument()
    expect(bodyOf(callsTo(fetchMock, 'POST /api/chat')[0]).message).toBe('Como funciona o pagamento?')
  })

  it('backend fora do ar: cabeçalho "Indisponível" e aviso para iniciar o atendimento', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    render(<ChatPage />)

    expect((await screen.findAllByText('Indisponível')).length).toBeGreaterThan(0)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Não foi possível iniciar o atendimento/)
  })
})
