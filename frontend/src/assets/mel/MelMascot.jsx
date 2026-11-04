import { useId } from 'react'
import { getAnimationMeta } from './melAnimations.js'

/**
 * Componente da mascote Mel com suporte às 5 animações musicais distintas:
 *
 * 1. dançando ('dancing') - balanço suave, bracinhos ritmados e notas flutuando.
 * 2. tocando ukulele ('ukulele') - segurando ukulele com dedilhado no ritmo e notas.
 * 3. cantando ('singing') - boquinha animada cantando, olhos alegres e notas subindo.
 * 4. curtindo música ('headphones') - com fones de ouvido, olhos fechados e balanço relaxado.
 * 5. surpresa musical ('surprise') - expressão alegre de surpresa, bracinhos nas bochechas e explosão de notas/brilhos.
 */
export default function MelMascot({
  animation = 'ukulele',
  size = 140,
  className = '',
  showLabel = false,
}) {
  // IDs únicos por instância: vários SVGs da Mel na página não podem compartilhar gradientes
  // (um SVG oculto, como o avatar do cabeçalho mobile, deixaria os outros sem cor).
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const ref = (name) => `mel-${uid}-${name}`

  const meta = getAnimationMeta(animation)
  const animKey = meta.id

  const s = typeof size === 'number' ? `${size}px` : size

  return (
    <div
      className={`mel-mascot mel-mascot--${animKey} ${className}`.trim()}
      style={{ width: s, height: s }}
      role="img"
      aria-label={meta.label}
    >
      <svg
        viewBox="0 0 200 200"
        width="100%"
        height="100%"
        className="mel-svg"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          {/* Sombra difusa da Mel */}
          <radialGradient id={ref('ground-shadow')} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#1a0414" stopOpacity="0.45" />
            <stop offset="70%" stopColor="#1a0414" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#1a0414" stopOpacity="0" />
          </radialGradient>

          {/* Gradiente principal 3D do corpo da Mel */}
          <radialGradient id={ref('body-gradient')} cx="36%" cy="26%" r="74%">
            <stop offset="0%" stopColor="#ff8cc8" />
            <stop offset="25%" stopColor="#f8379a" />
            <stop offset="60%" stopColor="#d4239a" />
            <stop offset="86%" stopColor="#9b30d9" />
            <stop offset="100%" stopColor="#5b21b6" />
          </radialGradient>

          {/* Brilho especular no topo */}
          <linearGradient id={ref('body-specular')} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>

          {/* Gradiente dos bracinhos */}
          <radialGradient id={ref('arm-gradient')} cx="35%" cy="30%" r="70%">
            <stop offset="0%" stopColor="#ff8cc8" />
            <stop offset="45%" stopColor="#f0369e" />
            <stop offset="100%" stopColor="#8b2fc9" />
          </radialGradient>

          {/* Flor - pétalas */}
          <linearGradient id={ref('flower-petal')} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ff3865" />
            <stop offset="50%" stopColor="#ea1342" />
            <stop offset="100%" stopColor="#9c0628" />
          </linearGradient>

          {/* Flor - miolo */}
          <radialGradient id={ref('flower-pistil')} cx="40%" cy="40%" r="60%">
            <stop offset="0%" stopColor="#fff580" />
            <stop offset="60%" stopColor="#ffcc00" />
            <stop offset="100%" stopColor="#d47a00" />
          </radialGradient>

          {/* Madeira do Ukulele */}
          <linearGradient id={ref('ukulele-wood')} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#e39a58" />
            <stop offset="50%" stopColor="#b86927" />
            <stop offset="100%" stopColor="#75390c" />
          </linearGradient>

          {/* Fones de ouvido */}
          <linearGradient id={ref('headphone-band')} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e1c26" />
            <stop offset="50%" stopColor="#3d384c" />
            <stop offset="100%" stopColor="#1e1c26" />
          </linearGradient>

          <radialGradient id={ref('headphone-cup')} cx="40%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#4f4a60" />
            <stop offset="70%" stopColor="#252230" />
            <stop offset="100%" stopColor="#14121a" />
          </radialGradient>

          {/* Gradiente das notas musicais */}
          <linearGradient id={ref('note-grad-pink')} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ff70b5" />
            <stop offset="100%" stopColor="#d91674" />
          </linearGradient>

          <linearGradient id={ref('note-grad-gold')} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffe680" />
            <stop offset="100%" stopColor="#f59e0b" />
          </linearGradient>
        </defs>

        {/* Sombra de apoio no chão */}
        <ellipse cx="100" cy="182" rx="55" ry="11" fill={`url(#${ref('ground-shadow')})`} className="mel-shadow" />

        {/* Grupo principal animado da Mel (balanço, pulo ou rotação) */}
        <g className="mel-character">
          {/* Pezinhos pequenos e discretos sob o corpo */}
          <ellipse cx="85" cy="176" rx="9" ry="5" fill="#2d061c" />
          <ellipse cx="115" cy="176" rx="9" ry="5" fill="#2d061c" />

          {/* Fone de ouvido - arco posterior (quando curtindo música) */}
          {animKey === 'headphones' ? (
            <path
              d="M 52,95 C 48,42 152,42 148,95"
              fill="none"
              stroke={`url(#${ref('headphone-band')})`}
              strokeWidth="9"
              strokeLinecap="round"
            />
          ) : null}

          {/* Corpo em formato de gota/blob da Mel */}
          <path
            d="M 100,42
               C 126,42 150,68 158,105
               C 167,144 163,168 138,174
               C 114,178 86,178 62,174
               C 37,168 33,144 42,105
               C 50,68 74,42 100,42 Z"
            fill={`url(#${ref('body-gradient')})`}
            className="mel-body-mesh"
          />

          {/* Brilho suave 3D de topo */}
          <ellipse
            cx="88"
            cy="65"
            rx="30"
            ry="16"
            fill={`url(#${ref('body-specular')})`}
            transform="rotate(-18 88 65)"
          />

          {/* ================= OLHOS ================= */}
          {/* Olhos normais (Ukulele, Surpresa) */}
          {animKey === 'ukulele' || animKey === 'surprise' ? (
            <g className="mel-eyes mel-eyes--wide">
              {/* Olho esquerdo */}
              <ellipse
                cx="88"
                cy="108"
                rx={animKey === 'surprise' ? '7.5' : '6.5'}
                ry={animKey === 'surprise' ? '12.5' : '11'}
                fill="#13040e"
              />
              <ellipse
                cx="85.5"
                cy={animKey === 'surprise' ? '104' : '105'}
                rx={animKey === 'surprise' ? '3' : '2.5'}
                ry={animKey === 'surprise' ? '4.5' : '4'}
                fill="#ffffff"
              />
              {animKey === 'surprise' ? (
                <ellipse cx="90.5" cy="112" rx="1.5" ry="1.5" fill="#ffffff" opacity="0.8" />
              ) : null}

              {/* Olho direito */}
              <ellipse
                cx="112"
                cy="108"
                rx={animKey === 'surprise' ? '7.5' : '6.5'}
                ry={animKey === 'surprise' ? '12.5' : '11'}
                fill="#13040e"
              />
              <ellipse
                cx="109.5"
                cy={animKey === 'surprise' ? '104' : '105'}
                rx={animKey === 'surprise' ? '3' : '2.5'}
                ry={animKey === 'surprise' ? '4.5' : '4'}
                fill="#ffffff"
              />
              {animKey === 'surprise' ? (
                <ellipse cx="114.5" cy="112" rx="1.5" ry="1.5" fill="#ffffff" opacity="0.8" />
              ) : null}
            </g>
          ) : null}

          {/* Olhos alegres em arco (Dançando, Cantando) */}
          {animKey === 'dancing' || animKey === 'singing' ? (
            <g className="mel-eyes mel-eyes--happy">
              <path
                d="M 81,110 Q 88,101 95,110"
                fill="none"
                stroke="#150510"
                strokeWidth="3.4"
                strokeLinecap="round"
              />
              <path
                d="M 105,110 Q 112,101 119,110"
                fill="none"
                stroke="#150510"
                strokeWidth="3.4"
                strokeLinecap="round"
              />
            </g>
          ) : null}

          {/* Olhos fechados e tranquilos (Curtindo música com fone) */}
          {animKey === 'headphones' ? (
            <g className="mel-eyes mel-eyes--serene">
              <path
                d="M 82,110 Q 88,117 94,110"
                fill="none"
                stroke="#150510"
                strokeWidth="3.2"
                strokeLinecap="round"
              />
              <path
                d="M 106,110 Q 112,117 118,110"
                fill="none"
                stroke="#150510"
                strokeWidth="3.2"
                strokeLinecap="round"
              />
            </g>
          ) : null}

          {/* ================= BOCA / EXPRESSÃO ================= */}
          {animKey === 'singing' ? (
            /* Boca cantando ritmada */
            <g className="mel-mouth mel-mouth--singing">
              <ellipse cx="100" cy="127" rx="6.5" ry="8.5" fill="#1b0512" />
              <path d="M 96,129 Q 100,134 104,129" fill="#ff5797" />
            </g>
          ) : animKey === 'surprise' ? (
            /* Boca de surpresa alegre */
            <g className="mel-mouth mel-mouth--surprise">
              <ellipse cx="100" cy="128" rx="5" ry="6.5" fill="#1b0512" />
            </g>
          ) : (
            /* Sorriso sutil e doce (Ukulele, Dançando, Fone) */
            <g className="mel-mouth mel-mouth--smile">
              <path
                d="M 95,124 Q 100,129 105,124"
                fill="none"
                stroke="#4a052c"
                strokeWidth="2.2"
                strokeLinecap="round"
              />
            </g>
          )}

          {/* Bochechinhas coradas suaves */}
          <ellipse cx="76" cy="118" rx="6" ry="3.5" fill="#ff3b88" opacity="0.38" />
          <ellipse cx="124" cy="118" rx="6" ry="3.5" fill="#ff3b88" opacity="0.38" />

          {/* ================= ACESSÓRIOS / BRAÇOS CONFORME ANIMAÇÃO ================= */}

          {/* Animação: TOCANDO UKULELE */}
          {animKey === 'ukulele' ? (
            <g className="mel-prop-ukulele">
              {/* Ukulele */}
              <g transform="translate(72, 118) rotate(-16)">
                {/* Corpo do ukulele em formato 8 */}
                <ellipse cx="28" cy="24" rx="14" ry="12" fill={`url(#${ref('ukulele-wood')})`} />
                <ellipse cx="16" cy="21" rx="10" ry="9" fill={`url(#${ref('ukulele-wood')})`} />
                {/* Boca do ukulele */}
                <circle cx="22" cy="22" r="4.2" fill="#2b1104" />
                {/* Cavalete */}
                <rect x="33" y="19" width="3" height="7" rx="1" fill="#301306" />
                {/* Braço / escala */}
                <rect x="-8" y="19" width="25" height="4.5" rx="1" fill="#4d2208" />
                {/* Headstock */}
                <polygon points="-8,18 -16,17 -16,25 -8,24" fill="#381705" />
                {/* Cordas finas */}
                <line x1="-12" y1="20" x2="33" y2="20.5" stroke="#ffffff" strokeWidth="0.7" opacity="0.85" />
                <line x1="-12" y1="21.5" x2="33" y2="22" stroke="#ffffff" strokeWidth="0.7" opacity="0.85" />
                <line x1="-12" y1="23" x2="33" y2="23.5" stroke="#ffffff" strokeWidth="0.7" opacity="0.85" />
              </g>

              {/* Braço esquerdo segurando o braço do ukulele */}
              <ellipse
                cx="66"
                cy="132"
                rx="14"
                ry="10"
                fill={`url(#${ref('arm-gradient')})`}
                transform="rotate(25 66 132)"
              />

              {/* Braço direito dedilhando no ritmo */}
              <g className="mel-arm-strumming">
                <ellipse
                  cx="128"
                  cy="132"
                  rx="15"
                  ry="10"
                  fill={`url(#${ref('arm-gradient')})`}
                  transform="rotate(-28 128 132)"
                />
              </g>
            </g>
          ) : null}

          {/* Animação: DANÇANDO */}
          {animKey === 'dancing' ? (
            <g className="mel-prop-dancing">
              {/* Braço esquerdo levantado no ritmo */}
              <ellipse
                cx="50"
                cy="118"
                rx="15"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                className="mel-arm-dance-left"
              />
              {/* Braço direito aberto */}
              <ellipse
                cx="150"
                cy="124"
                rx="15"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                className="mel-arm-dance-right"
              />
            </g>
          ) : null}

          {/* Animação: CANTANDO */}
          {animKey === 'singing' ? (
            <g className="mel-prop-singing">
              {/* Bracinhos repousando suavemente no corpo */}
              <ellipse
                cx="64"
                cy="136"
                rx="13"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                transform="rotate(30 64 136)"
              />
              <ellipse
                cx="136"
                cy="136"
                rx="13"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                transform="rotate(-30 136 136)"
              />
            </g>
          ) : null}

          {/* Animação: COM FONES DE OUVIDO */}
          {animKey === 'headphones' ? (
            <g className="mel-prop-headphones">
              {/* Almofadas dos fones cobrindo as laterais */}
              <g transform="translate(42, 92)">
                <rect x="0" y="0" width="13" height="26" rx="6" fill={`url(#${ref('headphone-cup')})`} />
                <rect x="1" y="2" width="4" height="22" rx="2" fill="#585268" opacity="0.6" />
              </g>
              <g transform="translate(145, 92)">
                <rect x="0" y="0" width="13" height="26" rx="6" fill={`url(#${ref('headphone-cup')})`} />
                <rect x="8" y="2" width="4" height="22" rx="2" fill="#585268" opacity="0.6" />
              </g>

              {/* Bracinhos relaxados */}
              <ellipse
                cx="66"
                cy="140"
                rx="13"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                transform="rotate(25 66 140)"
              />
              <ellipse
                cx="134"
                cy="140"
                rx="13"
                ry="9"
                fill={`url(#${ref('arm-gradient')})`}
                transform="rotate(-25 134 140)"
              />
            </g>
          ) : null}

          {/* Animação: SURPRESA MUSICAL */}
          {animKey === 'surprise' ? (
            <g className="mel-prop-surprise">
              {/* As duas mãozinhas na altura das bochechas/peito */}
              <ellipse
                cx="72"
                cy="128"
                rx="13"
                ry="10"
                fill={`url(#${ref('arm-gradient')})`}
                className="mel-arm-surprise-left"
              />
              <ellipse
                cx="128"
                cy="128"
                rx="13"
                ry="10"
                fill={`url(#${ref('arm-gradient')})`}
                className="mel-arm-surprise-right"
              />
            </g>
          ) : null}

          {/* Flor vermelha icônica da Mel (no topo esquerdo da cabeça) */}
          <g transform="translate(56, 54) rotate(-14)" className="mel-flower">
            {/* 5 pétalas arredondadas em carmim/vermelho */}
            <circle cx="-8" cy="0" r="8" fill={`url(#${ref('flower-petal')})`} />
            <circle cx="8" cy="0" r="8" fill={`url(#${ref('flower-petal')})`} />
            <circle cx="0" cy="-8" r="8" fill={`url(#${ref('flower-petal')})`} />
            <circle cx="-5.5" cy="6" r="8" fill={`url(#${ref('flower-petal')})`} />
            <circle cx="5.5" cy="6" r="8" fill={`url(#${ref('flower-petal')})`} />
            {/* Miolo dourado radiante */}
            <circle cx="0" cy="0" r="4.8" fill={`url(#${ref('flower-pistil')})`} />
            <circle cx="1" cy="-1" r="1.4" fill="#ffffff" opacity="0.85" />
          </g>
        </g>

        {/* ================= NOTAS E ELEMENTOS MUSICAIS FLUTUANTES ================= */}
        <g className="mel-musical-notes">
          {/* Nota 1 (Dourada / Colcheia) */}
          <g className="mel-note mel-note--1">
            <ellipse cx="148" cy="64" rx="4.5" ry="3.5" fill={`url(#${ref('note-grad-gold')})`} transform="rotate(-25 148 64)" />
            <rect x="150" y="47" width="2" height="17" fill={`url(#${ref('note-grad-gold')})`} />
            <path d="M 152,47 Q 159,51 158,57" fill="none" stroke={`url(#${ref('note-grad-gold')})`} strokeWidth="2" strokeLinecap="round" />
          </g>

          {/* Nota 2 (Rosa / Duas Colcheias ligadas) */}
          <g className="mel-note mel-note--2">
            <ellipse cx="42" cy="74" rx="4" ry="3" fill={`url(#${ref('note-grad-pink')})`} transform="rotate(-25 42 74)" />
            <ellipse cx="53" cy="70" rx="4" ry="3" fill={`url(#${ref('note-grad-pink')})`} transform="rotate(-25 53 70)" />
            <rect x="44" y="58" width="1.8" height="15" fill={`url(#${ref('note-grad-pink')})`} />
            <rect x="55" y="54" width="1.8" height="15" fill={`url(#${ref('note-grad-pink')})`} />
            <polygon points="44,58 57,54 57,57 44,61" fill={`url(#${ref('note-grad-pink')})`} />
          </g>

          {/* Nota 3 (Semínima suave) */}
          <g className="mel-note mel-note--3">
            <ellipse cx="162" cy="112" rx="4" ry="3" fill={`url(#${ref('note-grad-pink')})`} transform="rotate(-25 162 112)" />
            <rect x="164" y="98" width="1.8" height="13" fill={`url(#${ref('note-grad-pink')})`} />
          </g>

          {/* Brilhos / Estrelas para a animação Surpresa */}
          {animKey === 'surprise' ? (
            <g className="mel-sparks">
              <path
                d="M 152,40 Q 155,48 162,50 Q 155,52 152,60 Q 149,52 142,50 Q 149,48 152,40 Z"
                fill={`url(#${ref('note-grad-gold')})`}
                className="mel-spark-1"
              />
              <path
                d="M 38,98 Q 40,103 45,105 Q 40,107 38,112 Q 36,107 31,105 Q 36,103 38,98 Z"
                fill={`url(#${ref('note-grad-pink')})`}
                className="mel-spark-2"
              />
            </g>
          ) : null}
        </g>
      </svg>

      {showLabel ? <span className="mel-mascot__caption">{meta.name}</span> : null}
    </div>
  )
}

