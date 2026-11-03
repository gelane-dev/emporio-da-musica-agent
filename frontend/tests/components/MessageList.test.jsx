import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import MessageList from '../../src/components/chat/MessageList.jsx'
import { SUGGESTIONS } from '../../src/data/demo.js'

const MESSAGES = [
  { id: '1', role: 'assistant', text: 'Olá! Eu sou a Mel.', createdAt: '2026-03-25T13:00:00Z' },
  { id: '2', role: 'user', text: 'Tem violão?', createdAt: '2026-03-25T13:01:00Z' },
  { id: '3', role: 'notice', text: 'O atendimento foi reiniciado.', createdAt: '2026-03-25T13:02:00Z' },
]

function renderList(props = {}) {
  const handlers = { onRetry: vi.fn(), onDismissError: vi.fn(), onOpenProduct: vi.fn(), onSuggestion: vi.fn() }
  render(
    <MessageList messages={MESSAGES} isSending={false} error="" showSuggestions={false} {...handlers} {...props} />,
  )
  return handlers
}

describe('MessageList', () => {
  it('mostra as mensagens do cliente, da Mel e os avisos do sistema', () => {
    renderList()

    expect(screen.getByText('Olá! Eu sou a Mel.')).toBeInTheDocument()
    expect(screen.getByText('Tem violão?')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('O atendimento foi reiniciado.')
  })

  it('mostra o indicador de digitação enquanto aguarda a resposta', () => {
    renderList({ isSending: true })
    expect(screen.getByLabelText('Assistente está respondendo')).toBeInTheDocument()
  })

  it('mostra o erro com "Tentar de novo" e "Fechar"', async () => {
    const { onRetry, onDismissError } = renderList({ error: 'Falhou.' })

    expect(screen.getByRole('alert')).toHaveTextContent('Falhou.')
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(onRetry).toHaveBeenCalledOnce()
    expect(onDismissError).toHaveBeenCalledOnce()
  })

  it('omite "Tentar de novo" quando o erro não admite nova tentativa', () => {
    renderList({ error: 'Mensagem inválida.', onRetry: undefined })
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).not.toBeInTheDocument()
  })

  it('sugestões enviam o texto escolhido e somem durante o envio', async () => {
    const { onSuggestion } = renderList({ showSuggestions: true })

    await userEvent.click(screen.getByRole('button', { name: SUGGESTIONS[1] }))
    expect(onSuggestion).toHaveBeenCalledWith(SUGGESTIONS[1])
  })

  it('não mostra sugestões enquanto a resposta está em andamento', () => {
    renderList({ showSuggestions: true, isSending: true })
    expect(screen.queryByRole('button', { name: SUGGESTIONS[0] })).not.toBeInTheDocument()
  })
})
