import { useState } from 'react'
import { IconPickup, IconSearchLg, IconSoundWave, IconTuningFork } from '../icons.jsx'
import InstrumentFigure from './InstrumentFigure.jsx'

function SpecIcon({ label }) {
  const norm = String(label || '').toLowerCase()
  if (norm.includes('corpo')) return <IconSoundWave />
  if (norm.includes('captador')) return <IconPickup />
  if (norm.includes('escala') || norm.includes('braço')) return <IconTuningFork />
  return <IconSoundWave />
}

export default function ProductCard({ product, layout = 'chat', onOpen }) {
  const [imgFailed, setImgFailed] = useState(false)

  return (
    <article className={`product-card product-card--${layout}`}>
      <div className="product-card__media">
        {product.image && !imgFailed ? (
          <img
            src={product.image}
            alt={product.name}
            className="product-card__photo"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <InstrumentFigure product={product} />
        )}
        {product.featured ? <span className="product-card__badge">{product.highlight || 'Destaque'}</span> : null}
      </div>

      <div className="product-card__body">
        {/* Mobile Header */}
        <p className="product-card__brand">{product.brand}</p>
        <h3 className="product-card__title product-card__title--mobile">{product.name}</h3>
        {/* Desktop Header */}
        <h3 className="product-card__title product-card__title--desktop">{product.shortName || product.name}</h3>

        <p className="product-card__finish product-card__finish--mobile">
          {product.mobileFinish || product.finish}
        </p>
        <p className="product-card__finish product-card__finish--desktop">{product.finish}</p>

        {product.specs ? (
          <ul className="product-card__specs">
            {product.specs.slice(0, 3).map((spec) => (
              <li key={spec.label}>
                <span className="product-card__spec-icon" aria-hidden="true">
                  <SpecIcon label={spec.label} />
                </span>
                <span className="product-card__spec-text">
                  <strong>{spec.label}:</strong> {spec.value}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="product-card__desc">{product.description}</p>
        )}

        <div className="product-card__footer">
          <p className="product-card__price">{product.price}</p>
          <button type="button" className="product-card__cta product-card__cta--mobile" onClick={() => onOpen(product)}>
            Ver especificações ›
          </button>
          <button type="button" className="product-card__cta product-card__cta--desktop" onClick={() => onOpen(product)}>
            <IconSearchLg /> Ver detalhes
          </button>
        </div>

        {product.available ? (
          <p className="product-card__stock">
            <span className="stock-dot" /> Em estoque
          </p>
        ) : null}
      </div>
    </article>
  )
}

