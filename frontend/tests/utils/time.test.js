import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatTime, formatWhen, lastPreview } from '../../src/utils/time.js'

describe('utils/time', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('formatTime devolve hora:minuto e vazio para datas inválidas', () => {
    expect(formatTime(new Date(2026, 2, 25, 9, 5).toISOString())).toBe('09:05')
    expect(formatTime('não é data')).toBe('')
  })

  it('formatWhen: hora para hoje, "Ontem" e data curta para dias anteriores', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 2, 25, 15, 0))

    expect(formatWhen(new Date(2026, 2, 25, 9, 5).toISOString())).toBe('09:05')
    expect(formatWhen(new Date(2026, 2, 24, 9, 5).toISOString())).toBe('Ontem')
    expect(formatWhen(new Date(2026, 2, 10, 9, 5).toISOString())).toMatch(/^10/)
    expect(formatWhen('')).toBe('')
  })

  it('lastPreview usa a última mensagem com texto', () => {
    expect(
      lastPreview({
        messages: [
          { text: 'primeira' },
          { text: 'última' },
          { text: '', products: [{}] },
        ],
      }),
    ).toBe('última')
    expect(lastPreview({ messages: [] })).toBe('Conversa com o assistente')
  })
})
