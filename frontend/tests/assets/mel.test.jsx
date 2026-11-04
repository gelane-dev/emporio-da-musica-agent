import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MelAvatar from '../../src/assets/mel/MelAvatar.jsx'
import MelMascot from '../../src/assets/mel/MelMascot.jsx'
import { MEL_ANIMATIONS, getAnimationMeta, selectNextAnimation } from '../../src/assets/mel/melAnimations.js'
import MelWelcomeStage from '../../src/components/chat/MelWelcomeStage.jsx'

const IDS = MEL_ANIMATIONS.map((item) => item.id)

/** Todo `url(#id)` usado no SVG precisa apontar para um id definido no MESMO SVG. */
function expectSelfContainedGradients(svg) {
  const defined = new Set([...svg.querySelectorAll('[id]')].map((node) => node.id))
  const used = [...svg.querySelectorAll('*')]
    .flatMap((node) => ['fill', 'stroke'].map((attr) => node.getAttribute(attr)))
    .filter((value) => value?.startsWith('url(#'))
    .map((value) => value.slice(5, -1))
  expect(used.length).toBeGreaterThan(0)
  for (const id of used) expect(defined.has(id)).toBe(true)
  return defined
}

describe('catálogo de animações da Mel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('tem cinco animações distintas, todas com rótulo acessível', () => {
    expect(IDS).toEqual(['dancing', 'ukulele', 'singing', 'headphones', 'surprise'])
    expect(new Set(MEL_ANIMATIONS.map((item) => item.label)).size).toBe(5)
  })

  it.each(IDS)('nunca repete "%s" logo em seguida', (previous) => {
    for (let i = 0; i < 50; i += 1) {
      expect(selectNextAnimation(previous)).not.toBe(previous)
    }
  })

  it('chamadas seguidas sem informar a anterior também não repetem', () => {
    let last = selectNextAnimation()
    for (let i = 0; i < 100; i += 1) {
      const next = selectNextAnimation()
      expect(next).not.toBe(last)
      last = next
    }
  })

  it('todas as cinco podem ser sorteadas', () => {
    const seen = new Set()
    // Percorre o intervalo de Math.random de forma determinística.
    for (let i = 0; i < 40; i += 1) {
      vi.spyOn(Math, 'random').mockReturnValueOnce((i % 8) / 8)
      seen.add(selectNextAnimation(i % 2 ? 'dancing' : 'surprise'))
    }
    expect([...seen].sort()).toEqual([...IDS].sort())
  })

  it('id desconhecido cai na primeira animação', () => {
    expect(getAnimationMeta('inexistente').id).toBe('dancing')
  })
})

describe('MelMascot', () => {
  it.each(IDS)('renderiza a animação "%s" com rótulo e classe próprios', (id) => {
    const { container } = render(<MelMascot animation={id} size={80} />)
    const figure = screen.getByRole('img', { name: getAnimationMeta(id).label })
    expect(figure).toHaveClass(`mel-mascot--${id}`)
    expectSelfContainedGradients(container.querySelector('svg'))
  })

  it('cada animação tem seus elementos característicos (mesma personagem)', () => {
    const parts = (id) => {
      const { container, unmount } = render(<MelMascot animation={id} />)
      const found = {
        ukulele: Boolean(container.querySelector('.mel-prop-ukulele')),
        headphones: Boolean(container.querySelector('.mel-prop-headphones')),
        singingMouth: Boolean(container.querySelector('.mel-mouth--singing')),
        sparks: Boolean(container.querySelector('.mel-sparks')),
        danceArms: Boolean(container.querySelector('.mel-arm-dance-left')),
        flower: Boolean(container.querySelector('.mel-flower')),
      }
      unmount()
      return found
    }
    expect(parts('ukulele')).toMatchObject({ ukulele: true, headphones: false, flower: true })
    expect(parts('headphones')).toMatchObject({ headphones: true, ukulele: false, flower: true })
    expect(parts('singing')).toMatchObject({ singingMouth: true, flower: true })
    expect(parts('surprise')).toMatchObject({ sparks: true, flower: true })
    expect(parts('dancing')).toMatchObject({ danceArms: true, flower: true })
  })

  it('várias instâncias na página não compartilham ids de gradiente', () => {
    const { container } = render(
      <>
        <MelMascot animation="ukulele" />
        <MelMascot animation="surprise" />
      </>,
    )
    const [first, second] = container.querySelectorAll('svg')
    const a = expectSelfContainedGradients(first)
    const b = expectSelfContainedGradients(second)
    expect([...a].filter((id) => b.has(id))).toEqual([])
  })
})

describe('MelAvatar', () => {
  it('é uma imagem acessível da Mel com gradientes próprios por instância', () => {
    const { container } = render(
      <>
        <MelAvatar size={24} />
        <MelAvatar size={42} />
      </>,
    )
    expect(screen.getAllByRole('img', { name: 'Mel — Assistente do Empório da Música' })).toHaveLength(2)
    const [first, second] = container.querySelectorAll('svg')
    const a = expectSelfContainedGradients(first)
    const b = expectSelfContainedGradients(second)
    expect([...a].filter((id) => b.has(id))).toEqual([])
  })
})

describe('MelWelcomeStage', () => {
  it('apresenta a Mel com a animação da conversa, sem emojis', () => {
    render(<MelWelcomeStage animation="headphones" />)
    const stage = screen.getByRole('complementary', { name: 'Apresentação da Mel' })
    expect(within(stage).getByRole('img', { name: 'Mel curtindo música com fones de ouvido' })).toBeInTheDocument()
    expect(within(stage).getByText('Olá! Eu sou a Mel!')).toBeInTheDocument()
    // Emojis (🎵 🎤 🎧 ✨…) renderizam diferente em cada sistema; a nota ♪ é texto comum.
    expect(stage.textContent).not.toMatch(/[\u{1F300}-\u{1FAFF}\u{2728}]/u)
  })
})
