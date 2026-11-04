import { useEffect, useRef, useState } from 'react'
import MelAvatar from './MelAvatar.jsx'

const LABEL = 'Mel — Assistente do Empório da Música'

function hasWebGL() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

/**
 * Avatar da Mel com o modelo 3D real (mel_base_v04.glb), estático.
 *
 * Carregamento eficiente: o Three.js e o modelo só são baixados quando o avatar fica visível
 * (o avatar do cabeçalho mobile, oculto no desktop, nunca cria contexto WebGL). Até lá, e em
 * qualquer falha (sem WebGL, erro de rede), aparece o avatar 2D da Mel no mesmo lugar.
 */
export default function MelAvatar3D({ size = 42, className = '' }) {
  const hostRef = useRef(null)
  const [state, setState] = useState('fallback') // fallback | loading | ready
  const s = typeof size === 'number' ? `${size}px` : size

  useEffect(() => {
    const host = hostRef.current
    if (!host || typeof IntersectionObserver === 'undefined' || !hasWebGL()) return undefined

    let view = null
    let cancelled = false
    let resizeObserver = null

    async function start() {
      setState('loading')
      try {
        const { createMelView } = await import('./melScene.js')
        if (cancelled) return
        view = await createMelView(host)
        if (cancelled) {
          view.dispose()
          return
        }
        setState('ready')
        if (typeof ResizeObserver !== 'undefined') {
          resizeObserver = new ResizeObserver(() => view?.resize())
          resizeObserver.observe(host)
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Mel 3D indisponível; usando o avatar 2D.', error?.message ?? error)
          setState('fallback')
        }
      }
    }

    const visibility = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        visibility.disconnect()
        start()
      }
    })
    visibility.observe(host)

    return () => {
      cancelled = true
      visibility.disconnect()
      resizeObserver?.disconnect()
      view?.dispose()
    }
  }, [])

  return (
    <span
      ref={hostRef}
      className={`mel-avatar3d mel-avatar3d--${state} ${className}`.trim()}
      style={{ width: s, height: s, minWidth: s, minHeight: s }}
      role="img"
      aria-label={LABEL}
      title={LABEL}
      data-state={state}
    >
      {state !== 'ready' ? (
        <span className="mel-avatar3d__fallback" aria-hidden="true">
          <MelAvatar size="100%" alt="" />
        </span>
      ) : null}
    </span>
  )
}
