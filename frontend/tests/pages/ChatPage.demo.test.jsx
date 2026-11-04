import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ChatPage from '../../src/pages/ChatPage.jsx'

describe('ChatPage no modo demonstrativo', () => {
  it('sinaliza a demonstração, mostra conversas de exemplo e não chama a rede', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<ChatPage />)

    expect(screen.getByText('Modo demonstração')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(1)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('o detalhe do produto é rotulado como exemplo e não oferece carrinho, favoritos ou avaliações', async () => {
    vi.stubGlobal('fetch', vi.fn())
    render(<ChatPage />)

    await userEvent.click(screen.getAllByRole('button', { name: /Ver detalhes/ })[0])
    const dialog = screen.getByRole('dialog')

    expect(within(dialog).getByText(/Exemplo demonstrativo/)).toBeInTheDocument()
    // Características vêm dos dados do produto, não de um texto fixo.
    expect(within(dialog).getByText('Sons de alta definição')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /carrinho/i })).toBeNull()
    expect(within(dialog).queryByRole('button', { name: /Favoritar/i })).toBeNull()
    expect(within(dialog).queryByText(/avaliações/)).toBeNull()
    expect(within(dialog).getByRole('button', { name: /Conversar com a Mel/ })).toBeInTheDocument()
  })
})
