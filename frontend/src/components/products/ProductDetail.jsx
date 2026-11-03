import { useState } from 'react'
import {
  IconBack,
  IconCart,
  IconChat,
  IconDotsVertical,
  IconHeart,
  IconLeaf,
  IconShield,
  IconSoundWave,
  IconSparkle,
  IconTremolo,
  IconTruck,
  LyreMark,
} from '../icons.jsx'
import InstrumentFigure from './InstrumentFigure.jsx'

export default function ProductDetail({ product, onClose, onAsk }) {
  const [favorite, setFavorite] = useState(false)
  const [cartNotice, setCartNotice] = useState(false)
  const [imgFailed, setImgFailed] = useState(false)

  if (!product) return null
  const details = product.details ?? {}

  function handleCartClick() {
    setCartNotice(true)
  }

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
          <button
            type="button"
            className={`detail-heart ${favorite ? 'is-fav' : ''}`}
            onClick={() => setFavorite(!favorite)}
            aria-label="Favoritar instrumento"
          >
            <IconHeart />
          </button>
        </header>

        <section className="detail-hero">
          <div className="detail-watermark">{details.watermark || 'FENDER'}</div>
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
            {details.series || 'American Elite Series · 2024 · #US2401847'}
            <span>★ {details.rating || '4.9'} ({details.reviews || '87'} avaliações)</span>
          </p>
        </section>

        <ul className="detail-features">
          <li>
            <span className="detail-features__icon">
              <IconSoundWave />
            </span>
            <strong>Sons de alta definição</strong>
            <p>Voz Strat clássica com versatilidade moderna</p>
          </li>
          <li>
            <span className="detail-features__icon">
              <IconLeaf />
            </span>
            <strong>Corpo de Alburno</strong>
            <p>Leve e ressonante</p>
          </li>
          <li>
            <span className="detail-features__icon">
              <IconTremolo />
            </span>
            <strong>Sistema de Tremolo</strong>
            <p>Fender 2-Point Deluxe</p>
          </li>
          <li>
            <span className="detail-features__icon">
              <IconShield />
            </span>
            <strong>Acabamento Premium</strong>
            <p>Maple flameado com verniz poliuretano</p>
          </li>
        </ul>

        <aside className="detail-note">
          <header>
            <span className="detail-note__badge">
              <IconSparkle />
            </span>
            <strong>Assistente Empório</strong>
            <span className="detail-note__dots">
              <IconDotsVertical />
            </span>
          </header>
          <div className="detail-note__body">
            <p>
              {details.assistantNote ||
                'Essa é a Strat que você perguntou! Quer ver as especificações ou condições de pagamento?'}
            </p>
            <time>09:41</time>
          </div>
        </aside>

        {cartNotice ? (
          <div className="detail-cart-hint" role="status">
            <p>
              💡 No Empório da Música, nosso assistente cuida de orçamentos e reservas de forma personalizada.
            </p>
            <button type="button" onClick={handleDirectQuestion}>
              Perguntar ao assistente sobre compra e reserva
            </button>
          </div>
        ) : null}

        <div className="detail-actions">
          <button type="button" className="btn-cart" onClick={handleCartClick}>
            <IconCart /> Adicionar ao carrinho
          </button>
          <button type="button" className="btn-ask" onClick={handleDirectQuestion}>
            <IconChat /> Conversar com o assistente
          </button>
        </div>

        <footer className="detail-foot">
          <span>
            <IconTruck /> Envio rápido e seguro
          </span>
          <span className="detail-foot__divider">|</span>
          <span>
            <IconShield /> Garantia de 1 ano
          </span>
        </footer>
      </div>
    </div>
  )
}

