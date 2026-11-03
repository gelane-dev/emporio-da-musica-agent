import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Composer from '../../src/components/chat/Composer.jsx'

function setup(props = {}) {
  const onSend = vi.fn()
  render(<Composer disabled={false} onSend={onSend} {...props} />)
  return { onSend, input: screen.getByPlaceholderText('Digite sua mensagem...'), send: screen.getByRole('button', { name: 'Enviar' }) }
}

describe('Composer', () => {
  it('envia o texto sem espaços nas pontas com Enter e limpa o campo', async () => {
    const { onSend, input } = setup()

    await userEvent.type(input, '  Tem violão?  {Enter}')

    expect(onSend).toHaveBeenCalledExactlyOnceWith('Tem violão?')
    expect(input).toHaveValue('')
  })

  it('envia pelo botão', async () => {
    const { onSend, input, send } = setup()

    await userEvent.type(input, 'Oi')
    await userEvent.click(send)

    expect(onSend).toHaveBeenCalledWith('Oi')
  })

  it('Shift+Enter quebra a linha em vez de enviar', async () => {
    const { onSend, input } = setup()

    await userEvent.type(input, 'linha 1{Shift>}{Enter}{/Shift}linha 2')

    expect(onSend).not.toHaveBeenCalled()
    expect(input).toHaveValue('linha 1\nlinha 2')
  })

  it('mantém o botão desativado enquanto só houver espaços', async () => {
    const { onSend, input, send } = setup()

    expect(send).toBeDisabled()
    await userEvent.type(input, '   {Enter}')

    expect(send).toBeDisabled()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('bloqueia o envio enquanto a resposta anterior está em andamento', () => {
    const { input, send } = setup({ disabled: true })

    expect(input).toBeDisabled()
    expect(send).toBeDisabled()
  })

  it('mostra o contador perto do limite de 2000 caracteres da API', () => {
    const { input } = setup()

    fireEvent.change(input, { target: { value: 'a'.repeat(1799) } })
    expect(screen.queryByText(/\/2000/)).not.toBeInTheDocument()

    fireEvent.change(input, { target: { value: 'a'.repeat(1800) } })
    expect(screen.getByText('1800/2000')).toBeInTheDocument()
    expect(input).toHaveAttribute('maxLength', '2000')
  })
})
