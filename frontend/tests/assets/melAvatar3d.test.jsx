import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const scene = vi.hoisted(() => ({ createMelView: vi.fn() }))
vi.mock('../../src/assets/mel/melScene.js', () => scene)

import MelAvatar3D from '../../src/assets/mel/MelAvatar3D.jsx'

const LABEL = 'Mel — Assistente do Empório da Música'

/** IntersectionObserver falso: `visible` decide se o avatar entra na tela. */
function stubIntersection(visible) {
  const observers = []
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback) {
        this.callback = callback
        observers.push(this)
      }
      observe(target) {
        if (visible) queueMicrotask(() => this.callback([{ isIntersecting: true, target }]))
      }
      disconnect() {}
    },
  )
  return observers
}

function stubWebGL(available) {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => (available ? {} : null))
}

describe('MelAvatar3D', () => {
  beforeEach(() => {
    scene.createMelView.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sem suporte a IntersectionObserver mostra o avatar 2D e não carrega o 3D', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    render(<MelAvatar3D size={42} />)
    const avatar = screen.getByRole('img', { name: LABEL })
    expect(avatar).toHaveAttribute('data-state', 'fallback')
    expect(avatar.querySelector('.mel-avatar svg')).not.toBeNull()
    expect(scene.createMelView).not.toHaveBeenCalled()
  })

  it('sem WebGL fica no avatar 2D', async () => {
    stubIntersection(true)
    stubWebGL(false)
    render(<MelAvatar3D />)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.getByRole('img', { name: LABEL })).toHaveAttribute('data-state', 'fallback')
    expect(scene.createMelView).not.toHaveBeenCalled()
  })

  it('fora da tela (ex.: avatar do cabeçalho mobile no desktop) não cria contexto WebGL', async () => {
    stubIntersection(false)
    stubWebGL(true)
    render(<MelAvatar3D />)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(scene.createMelView).not.toHaveBeenCalled()
  })

  it('visível e com WebGL: troca o 2D pelo modelo 3D e libera o contexto ao desmontar', async () => {
    stubIntersection(true)
    stubWebGL(true)
    const dispose = vi.fn()
    scene.createMelView.mockImplementation(async (host) => {
      const canvas = document.createElement('canvas')
      canvas.className = 'mel-avatar3d__canvas'
      host.appendChild(canvas)
      return { resize: vi.fn(), dispose }
    })

    const { unmount } = render(<MelAvatar3D size={42} />)
    const avatar = screen.getByRole('img', { name: LABEL })
    await waitFor(() => expect(avatar).toHaveAttribute('data-state', 'ready'))
    expect(avatar.querySelector('canvas.mel-avatar3d__canvas')).not.toBeNull()
    expect(avatar.querySelector('.mel-avatar3d__fallback')).toBeNull()
    expect(scene.createMelView).toHaveBeenCalledTimes(1)

    unmount()
    expect(dispose).toHaveBeenCalledTimes(1)
  })

  it('se o modelo falhar ao carregar, volta ao avatar 2D sem quebrar a interface', async () => {
    stubIntersection(true)
    stubWebGL(true)
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    scene.createMelView.mockRejectedValue(new Error('404 mel_base_v04.glb'))

    render(<MelAvatar3D />)
    const avatar = screen.getByRole('img', { name: LABEL })
    await waitFor(() => expect(warn).toHaveBeenCalled())
    expect(avatar).toHaveAttribute('data-state', 'fallback')
    expect(avatar.querySelector('.mel-avatar svg')).not.toBeNull()
  })
})
