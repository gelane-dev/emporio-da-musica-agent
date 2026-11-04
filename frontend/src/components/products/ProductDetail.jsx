import { useState } from 'react'
import {
  IconBack,
  IconChat,
  IconLeaf,
  IconShield,
  IconSoundWave,
  IconTremolo,
  LyreMark,
} from '../icons.jsx'
import InstrumentFigure from './InstrumentFigure.jsx'
import MelAvatar from '../../assets/mel/MelAvatar.jsx'

const FEATURE_ICONS = [<IconSoundWave key="wave" />, <IconLeaf key="leaf" />, <IconTremolo key="tremolo" />, <IconShield key="shield" />]

export default function ProductDetail({ product, onClose, onAsk }) {
  const [imgFailed, setImgFailed] = useState(false)

  if (!product) return null
  const details = product.details ?? {}
  const features = Array.isArray(details.features) ? details.features : []

  function handleDirectQuestion() {
    onAsk(product)
  }

  return (
    <div className="detail-layer" role="dialog" aria-modal="true" aria-labelledby="detail-title">
      <div className="detail-sheet">
        <header className="detail-brand">
          <button type="button" className="ghost-link" onClick={onClose} aria-label="Voltar">
            <IconBack /> Voltar
          </button>
          <div className="detail-brand__center">
            <span className="detail-brand__lyre">
              <LyreMark size={28} />
            </span>
            <div className="detail-brand__title">
              <span>EMPÓRIO</span>
              <strong>DA MÚSICA</strong>
            </div>
          </div>
          <span className="detail-brand__spacer" aria-hidden="true" />
        </header>

        <section className="detail-hero">
          {details.watermark ? <div className="detail-watermark">{details.watermark}</div> : null}
          {product.image && !imgFailed ? (
            <img
              src={product.image}
              alt={product.name}
              className="detail-hero__photo"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <InstrumentFigure product={product} variant="hero" />
          )}
        </section>

        <section className="detail-copy">
          <h1 id="detail-title">{product.shortName || product.name}</h1>
          <p className="detail-meta">
            {details.series || 'Especificações, preço e disponibilidade com a Mel no atendimento'}
          </p>
        </section>

        {features.length > 0 ? (
          <ul className="detail-features">
            {features.map((feature, index) => (
              <li key={feature.title}>
                <span className="detail-features__icon">{FEATURE_ICONS[index % FEATURE_ICONS.length]}</span>
                <strong>{feature.title}</strong>
                <p>{feature.text}</p>
              </li>
            ))}
          </ul>
        ) : null}

        <aside className="detail-note">
          <header>
            <span className="detail-note__badge">
              <MelAvatar size={24} />
            </span>
            <strong>Mel — Assistente Musical</strong>
          </header>
          <div className="detail-note__body">
            <p>
              {details.assistantNote ||
                'Posso verificar disponibilidade, condições de pagamento e detalhes deste instrumento para você!'}
            </p>
          </div>
        </aside>

        <div className="detail-actions">
          <button type="button" className="btn-ask btn-ask--full" onClick={handleDirectQuestion}>
            <IconChat /> Conversar com a Mel sobre este instrumento
          </button>
        </div>

        <footer className="detail-foot">
          <span>Exemplo demonstrativo: preço, estoque e condições reais são confirmados pela Mel no atendimento.</span>
        </footer>
      </div>
    </div>
  )
}
