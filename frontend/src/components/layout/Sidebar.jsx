import { CATEGORIES } from '../../data/demo.js'
import { lastPreview, formatWhen } from '../../utils/time.js'
import { CategoryGlyph, GuitarMark, IconPlus, IconSearch, IconShield } from '../icons.jsx'
import MelAvatar from '../../assets/mel/MelAvatar.jsx'

export default function Sidebar({
  conversations,
  activeId,
  query,
  onQuery,
  onSelect,
  onNew,
  onCategory,
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <GuitarMark size={38} />
        <div>
          <h1>Empório da Música</h1>
          <p>Instrumentos musicais premium</p>
        </div>
      </div>

      <button type="button" className="new-chat" onClick={() => onNew()}>
        <IconPlus /> Nova conversa
      </button>

      <label className="search">
        <IconSearch />
        <input
          value={query}
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Buscar conversas..."
        />
      </label>

      <section className="sidebar-block">
        <header>
          <span>Conversas recentes</span>
        </header>
        <ul className="conversation-list">
          {conversations.length === 0 ? (
            <li className="conversation-empty">Nenhuma conversa encontrada.</li>
          ) : (
            conversations.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className={item.id === activeId ? 'is-active' : ''}
                  onClick={() => onSelect(item.id)}
                >
                  <span className="conversation-list__avatar">
                    {item.customer?.avatar ? (
                      <img src={item.customer.avatar} alt={item.customer.name || item.title} />
                    ) : (
                      <MelAvatar size={24} />
                    )}
                  </span>
                  <span className="conversation-list__copy">
                    <strong>{item.customer?.name || item.title}</strong>
                    <em>{lastPreview(item)}</em>
                  </span>
                  <span className="conversation-list__meta">
                    <time>{item.timeLabel || formatWhen(item.updatedAt)}</time>
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </section>

      <section className="sidebar-block">
        <header>
          <span>Categorias</span>
        </header>
        <ul className="category-list">
          {CATEGORIES.map((category) => (
            <li key={category.id}>
              <button type="button" onClick={() => onCategory(category.prompt)}>
                <span className="category-list__icon">
                  <CategoryGlyph name={category.id} />
                </span>
                {category.label}
                <span className="category-list__chevron">›</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <p className="sidebar-foot">
        <IconShield /> Atendimento especializado para músicos exigentes.
      </p>
    </aside>
  )
}
