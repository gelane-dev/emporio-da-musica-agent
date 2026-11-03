export default function InstrumentFigure({ product, variant = 'card' }) {
  const body = product.tone || '#c43c3c'
  const pickguard = variant === 'hero' ? '#f4eee6' : '#f7f1ea'
  return (
    <div className={`instrument-figure instrument-figure--${variant}`}>
      <svg viewBox="0 0 200 520" role="img" aria-label={`${product.brand} ${product.name}`}>
        <defs>
          <linearGradient id={`body-${product.id}`} x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#f2d2c4" />
            <stop offset="35%" stopColor={body} />
            <stop offset="100%" stopColor="#6a1b1b" />
          </linearGradient>
        </defs>
        <rect x="92" y="78" width="16" height="168" rx="4" fill="#d7c09a" />
        <rect x="88" y="78" width="24" height="10" rx="2" fill="#b08962" />
        <rect x="74" y="18" width="52" height="68" rx="10" fill="#c9a36c" />
        <rect x="80" y="24" width="8" height="10" rx="2" fill="#5b3b28" />
        <rect x="92" y="24" width="8" height="10" rx="2" fill="#5b3b28" />
        <rect x="104" y="24" width="8" height="10" rx="2" fill="#5b3b28" />
        <rect x="112" y="38" width="8" height="10" rx="2" fill="#5b3b28" />
        <rect x="112" y="52" width="8" height="10" rx="2" fill="#5b3b28" />
        <rect x="100" y="64" width="8" height="10" rx="2" fill="#5b3b28" />
        <path
          d="M100 240c-18 8-48 28-58 58-8 24 2 52 24 64 8 5 12 16 8 28-8 24 6 52 38 64 28 10 52-4 62-26 8-16 4-30-2-42 18-10 32-30 28-52-4-26-28-46-48-56 8-18 4-38-10-48-12-8-28-6-42 10z"
          fill={`url(#body-${product.id})`}
        />
        <path
          d="M78 292c18-22 44-28 62-10 8 8 10 20 4 32-18 14-42 12-58-4-8-8-10-12-8-18z"
          fill={pickguard}
        />
        <rect x="92" y="300" width="22" height="8" rx="2" fill="#d7c09a" />
        <rect x="94" y="316" width="18" height="7" rx="2" fill="#d7c09a" />
        <rect x="96" y="330" width="14" height="7" rx="2" fill="#d7c09a" />
        <circle cx="118" cy="348" r="5" fill="#efe6d8" />
        <circle cx="128" cy="362" r="5" fill="#efe6d8" />
        <circle cx="122" cy="376" r="5" fill="#efe6d8" />
        <rect x="86" y="392" width="40" height="9" rx="2" fill="#5b3b28" />
      </svg>
    </div>
  )
}
