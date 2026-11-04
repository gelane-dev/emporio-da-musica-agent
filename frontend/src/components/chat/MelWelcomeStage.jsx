import MelMascot from '../../assets/mel/MelMascot.jsx'
import { getAnimationMeta } from '../../assets/mel/melAnimations.js'

const MOOD_PHRASES = {
  dancing: 'Dançando com muita música para você! ♪',
  ukulele: 'No ritmo do ukulele para te atender! ♪',
  singing: 'Afinando as melhores respostas para sua dúvida! ♪',
  headphones: 'Sintonizada no melhor do atendimento musical! ♪',
  surprise: 'Pronta para te surpreender com nossos instrumentos! ♪',
}

export default function MelWelcomeStage({ animation = 'ukulele' }) {
  const meta = getAnimationMeta(animation)
  const phrase = MOOD_PHRASES[meta.id] || MOOD_PHRASES.ukulele

  return (
    <aside className="mel-welcome-stage" aria-label="Apresentação da Mel">
      <div className="mel-welcome-stage__figure">
        <MelMascot animation={meta.id} size={110} />
      </div>
      <div className="mel-welcome-stage__content">
        <span className="mel-welcome-stage__badge">
          <span className="mel-welcome-stage__badge-dot" />
          Assistente Musical
        </span>
        <h2 className="mel-welcome-stage__title">Olá! Eu sou a Mel!</h2>
        <p className="mel-welcome-stage__desc">
          Estou aqui para te ajudar a encontrar o instrumento ideal, tirar dúvidas sobre pedidos, pagamentos e muito mais.
        </p>
        <span className="mel-welcome-stage__mood">{phrase}</span>
      </div>
    </aside>
  )
}

