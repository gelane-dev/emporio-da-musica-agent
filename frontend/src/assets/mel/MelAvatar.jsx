import { useId } from 'react'
/**
 * Avatar oficial da mascote Mel para o Empório da Música.
 *
 * Enquadramento circular, nítido e reconhecível em qualquer tamanho (desktop e mobile).
 * Preserva as características principais: formato gota/blob, gradiente rosa/roxo 3D,
 * olhos pretos expressivos e flor vermelha com miolo dourado.
 */
export default function MelAvatar({ size = 36, className = '', alt = 'Mel — Assistente do Empório da Música' }) {
  // IDs únicos por instância: vários SVGs da Mel na página não podem compartilhar gradientes
  // (um SVG oculto, como o avatar do cabeçalho mobile, deixaria os outros sem cor).
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const ref = (name) => `mel-${uid}-${name}`

  const s = typeof size === 'number' ? `${size}px` : size

  return (
    <span
      className={`mel-avatar ${className}`.trim()}
      style={{ width: s, height: s, minWidth: s, minHeight: s }}
      role="img"
      aria-label={alt}
      title={alt}
    >
      <svg
        viewBox="0 0 100 100"
        width="100%"
        height="100%"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          {/* Fundo circular suave */}
          <radialGradient id={ref('bg')} cx="50%" cy="40%" r="60%">
            <stop offset="0%" stopColor="#3d152a" />
            <stop offset="70%" stopColor="#240c19" />
            <stop offset="100%" stopColor="#15060f" />
          </radialGradient>

          {/* Gradiente 3D do corpo da Mel */}
          <radialGradient id={ref('body')} cx="38%" cy="28%" r="72%">
            <stop offset="0%" stopColor="#ff8cc8" />
            <stop offset="28%" stopColor="#f8379a" />
            <stop offset="68%" stopColor="#c7259f" />
            <stop offset="100%" stopColor="#7c2fd0" />
          </radialGradient>

          {/* Brilho especular no topo da cabeça */}
          <linearGradient id={ref('highlight')} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>

          {/* Sombra de contato */}
          <radialGradient id={ref('shadow')} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#14020e" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#14020e" stopOpacity="0" />
          </radialGradient>

          {/* Gradiente das pétalas da flor */}
          <linearGradient id={ref('petal')} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ff3360" />
            <stop offset="60%" stopColor="#e51341" />
            <stop offset="100%" stopColor="#a3082b" />
          </linearGradient>

          {/* Miolo dourado da flor */}
          <radialGradient id={ref('pistil')} cx="40%" cy="40%" r="60%">
            <stop offset="0%" stopColor="#fff066" />
            <stop offset="60%" stopColor="#ffcc00" />
            <stop offset="100%" stopColor="#d98200" />
          </radialGradient>
        </defs>

        {/* Fundo circular escuro com leve borda */}
        <circle cx="50" cy="50" r="48" fill={`url(#${ref('bg')})`} stroke="#fa2d88" strokeWidth="1.5" strokeOpacity="0.35" />

        {/* Sombra de apoio na base */}
        <ellipse cx="50" cy="88" rx="28" ry="6" fill={`url(#${ref('shadow')})`} />

        {/* Corpo gota / blob da Mel */}
        <path
          d="M 50,18
             C 65,18 78,34 82,54
             C 87,74 84,86 70,88
             C 56,90 44,90 30,88
             C 16,86 13,74 18,54
             C 22,34 35,18 50,18 Z"
          fill={`url(#${ref('body')})`}
        />

        {/* Brilho suave no topo da cabeça */}
        <ellipse cx="44" cy="30" rx="16" ry="9" fill={`url(#${ref('highlight')})`} transform="rotate(-15 44 30)" />

        {/* Olhos pretos expressivos em formato oval com brilho de vidro */}
        {/* Olho esquerdo */}
        <ellipse cx="43" cy="55" rx="3.6" ry="6.2" fill="#140510" />
        <ellipse cx="41.8" cy="52.8" rx="1.3" ry="2.2" fill="#ffffff" />

        {/* Olho direito */}
        <ellipse cx="57" cy="55" rx="3.6" ry="6.2" fill="#140510" />
        <ellipse cx="55.8" cy="52.8" rx="1.3" ry="2.2" fill="#ffffff" />

        {/* Sorriso sutil e amigável */}
        <path
          d="M 47.5,67 Q 50,70 52.5,67"
          fill="none"
          stroke="#520531"
          strokeWidth="1.6"
          strokeLinecap="round"
        />

        {/* Flor vermelha característica no lado superior esquerdo */}
        <g transform="translate(24, 25) rotate(-12)">
          {/* 5 pétalas arredondadas */}
          <circle cx="-5" cy="0" r="5" fill={`url(#${ref('petal')})`} />
          <circle cx="5" cy="0" r="5" fill={`url(#${ref('petal')})`} />
          <circle cx="0" cy="-5" r="5" fill={`url(#${ref('petal')})`} />
          <circle cx="-3.5" cy="4" r="5" fill={`url(#${ref('petal')})`} />
          <circle cx="3.5" cy="4" r="5" fill={`url(#${ref('petal')})`} />
          {/* Miolo amarelo */}
          <circle cx="0" cy="0" r="3" fill={`url(#${ref('pistil')})`} />
          <circle cx="0.5" cy="-0.5" r="0.9" fill="#ffffff" opacity="0.8" />
        </g>
      </svg>
    </span>
  )
}

