import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Sidebar from '../../src/components/layout/Sidebar.jsx'
import { CATEGORIES } from '../../src/data/demo.js'

const CONVERSATIONS = [
  { id: 'a', title: 'Violões', updatedAt: '2026-03-25T13:00:00Z', messages: [{ id: '1', role: 'user', text: 'Tem violão?' }] },
  { id: 'b', title: 'Pedido 4', updatedAt: '2026-03-25T13:00:00Z', messages: [] },
]

function renderSidebar(props = {}) {
  const handlers = { onQuery: vi.fn(), onSelect: vi.fn(), onNew: vi.fn(), onCategory: vi.fn() }
  render(<Sidebar conversations={CONVERSATIONS} activeId="a" query="" {...handlers} {...props} />)
  return handlers
}

describe('Sidebar', () => {
  it('lista as conversas com a prévia da última mensagem e destaca a ativa', () => {
    renderSidebar()

    const active = screen.getByRole('button', { name: /Violões/ })
    expect(active).toHaveClass('is-active')
    expect(active).toHaveTextContent('Tem violão?')
    expect(screen.getByRole('button', { name: /Pedido 4/ })).toHaveTextContent('Conversa com o assistente')
  })

  it('seleciona uma conversa, cria uma nova e repassa a busca', async () => {
    const { onSelect, onNew, onQuery } = renderSidebar()

    await userEvent.click(screen.getByRole('button', { name: /Pedido 4/ }))
    await userEvent.click(screen.getByRole('button', { name: /Nova conversa/ }))
    await userEvent.type(screen.getByPlaceholderText('Buscar conversas...'), 'x')

    expect(onSelect).toHaveBeenCalledWith('b')
    expect(onNew).toHaveBeenCalledOnce()
    expect(onQuery).toHaveBeenCalledWith('x')
  })

  it('categorias iniciam uma conversa com a pergunta da categoria', async () => {
    const { onCategory } = renderSidebar()

    await userEvent.click(screen.getByRole('button', { name: new RegExp(CATEGORIES[0].label) }))

    expect(onCategory).toHaveBeenCalledWith(CATEGORIES[0].prompt)
  })

  it('avisa quando a busca não encontra conversas', () => {
    renderSidebar({ conversations: [] })
    expect(screen.getByText('Nenhuma conversa encontrada.')).toBeInTheDocument()
  })
})
