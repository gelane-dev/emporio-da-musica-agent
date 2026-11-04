import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ChatPanel from '../../src/components/chat/ChatPanel.jsx'
import { SUGGESTIONS } from '../../src/data/demo.js'

const GREETING = { id: 'g', role: 'assistant', text: 'Olá!', createdAt: '2026-03-25T13:00:00Z' }

function renderPanel(props = {}) {
  render(
    <ChatPanel
      conversation={{ id: 'c1', messages: [GREETING] }}
      isDemo={false}
      health={{ status: 'online', detail: null }}
      isSending={false}
      error=""
      canRetry={false}
      onSend={vi.fn()}
      onOpenProduct={vi.fn()}
      onOpenSidebar={vi.fn()}
      onDismissError={vi.fn()}
      onRetry={vi.fn()}
      {...props}
    />,
  )
}

describe('ChatPanel', () => {
  it.each([
    ['online', 'Online'],
    ['degraded', 'Atendimento degradado'],
    ['offline', 'Indisponível'],
    ['checking', 'Verificando…'],
  ])('mostra o estado do backend "%s" no cabeçalho', (status, label) => {
    renderPanel({ health: { status, detail: null } })
    expect(screen.getAllByText(label).length).toBeGreaterThan(0)
  })

  it('usa o detalhe do backend como dica quando o atendimento está degradado', () => {
    renderPanel({ health: { status: 'degraded', detail: 'GROQ_API_KEY ausente.' } })
    expect(screen.getByTitle('GROQ_API_KEY ausente.')).toBeInTheDocument()
  })

  it('sinaliza o modo demonstrativo no cabeçalho e no rodapé', () => {
    renderPanel({ isDemo: true })
    expect(screen.getByText('Modo demonstração')).toBeInTheDocument()
    expect(screen.getByText(/respostas fictícias, sem conexão com o agente/)).toBeInTheDocument()
  })

  it('mostra sugestões só antes da primeira mensagem do cliente', () => {
    renderPanel()
    expect(screen.getByRole('button', { name: SUGGESTIONS[0] })).toBeInTheDocument()
  })

  it('esconde as sugestões depois que o cliente escreve', () => {
    renderPanel({
      conversation: {
        id: 'c1',
        messages: [GREETING, { id: 'u', role: 'user', text: 'Oi', createdAt: '2026-03-25T13:01:00Z' }],
      },
    })
    expect(screen.queryByRole('button', { name: SUGGESTIONS[0] })).not.toBeInTheDocument()
  })

  it('oferece "Tentar de novo" só quando o erro permite', () => {
    renderPanel({ error: 'Falhou.', canRetry: false })
    expect(screen.queryByRole('button', { name: 'Tentar de novo' })).not.toBeInTheDocument()
  })
})

describe('ChatPanel com a Mel', () => {
  it('mostra a Mel no cabeçalho e nas mensagens e a apresentação com a animação da conversa', () => {
    renderPanel({ conversation: { id: 'c1', animation: 'singing', messages: [GREETING] } })
    // Cabeçalho: versão desktop e mobile (o CSS mostra uma de cada vez).
    const header = screen.getByRole('banner')
    expect(within(header).getAllByRole('img', { name: 'Mel — Assistente do Empório da Música' })).toHaveLength(2)
    // Mensagem da assistente: avatar decorativo (aria-hidden), ao lado do texto.
    const bubble = screen.getByText('Olá!').closest('.msg--assistant')
    expect(bubble.querySelector('.msg__avatar .mel-avatar')).not.toBeNull()
    expect(screen.getByRole('img', { name: 'Mel cantando' })).toBeInTheDocument()
  })

  it('não tem botões de perfil ou opções sem ação no backend', () => {
    renderPanel()
    expect(screen.queryByRole('button', { name: 'Perfil do usuário' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Mais opções' })).toBeNull()
  })
})
