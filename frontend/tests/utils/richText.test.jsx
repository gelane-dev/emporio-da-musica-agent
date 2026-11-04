import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MessageBubble from '../../src/components/chat/MessageBubble.jsx'
import { renderInlineMarkdown } from '../../src/utils/richText.jsx'

const at = '2026-03-25T13:00:00Z'

describe('negrito nas respostas da Mel', () => {
  it('troca **texto** por negrito sem mostrar os asteriscos e mantém o resto do texto', () => {
    const { container } = render(
      <MessageBubble message={{ id: '1', role: 'assistant', text: '**Preço**\n- Original: R$ 549,00', createdAt: at }} />,
    )
    const p = container.querySelector('.msg__bubble p')
    expect(p.querySelector('strong').textContent).toBe('Preço')
    expect(p.textContent).toBe('Preço\n- Original: R$ 549,00')
  })

  it('não interpreta HTML vindo da resposta', () => {
    const { container } = render(
      <MessageBubble message={{ id: '2', role: 'assistant', text: '**<img src=x onerror=alert(1)>** ok', createdAt: at }} />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('strong').textContent).toBe('<img src=x onerror=alert(1)>')
  })

  it('o texto do cliente fica literal', () => {
    const { container } = render(<MessageBubble message={{ id: '3', role: 'user', text: '**oi**', createdAt: at }} />)
    expect(container.querySelector('strong')).toBeNull()
    expect(container.querySelector('.msg__bubble p').textContent).toBe('**oi**')
  })

  it('texto sem marcação e asteriscos soltos ficam como estão', () => {
    expect(renderInlineMarkdown('sem negrito')).toBe('sem negrito')
    expect(renderInlineMarkdown('3 * 4 = 12 e ** sozinho')).toEqual(['3 * 4 = 12 e ** sozinho'])
  })
})
