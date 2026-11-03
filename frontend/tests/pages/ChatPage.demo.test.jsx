import { render, screen } from '@testing-library/react'
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
})
