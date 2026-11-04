import { IconMenu } from '../icons.jsx'
import Composer from './Composer.jsx'
import MessageList from './MessageList.jsx'
import MelAvatar3D from '../../assets/mel/MelAvatar3D.jsx'

const HEALTH_LABELS = {
  checking: { desktop: 'Verificando…', mobile: 'Verificando…', dot: 'status-dot--demo' },
  online: { desktop: 'Online', mobile: 'Online', dot: '' },
  degraded: { desktop: 'Atendimento degradado', mobile: 'Degradado', dot: 'status-dot--warn' },
  offline: { desktop: 'Indisponível', mobile: 'Indisponível', dot: 'status-dot--off' },
}

const HEALTH_TITLES = {
  checking: 'Verificando a conexão com o atendimento.',
  online: 'Conectado ao atendimento.',
  degraded: 'O servidor respondeu, mas o agente não está pronto.',
  offline: 'Não foi possível contatar o servidor do atendimento.',
}

export default function ChatPanel({
  conversation,
  isDemo,
  health,
  isSending,
  error,
  canRetry,
  onSend,
  onOpenProduct,
  onOpenSidebar,
  onDismissError,
  onRetry,
}) {
  const userTurns = conversation.messages.filter((item) => item.role === 'user').length
  const healthStatus = HEALTH_LABELS[health?.status] ? health.status : 'checking'
  const healthLabel = HEALTH_LABELS[healthStatus]

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <span className="chat-header__mark chat-header__mark--mobile">
          <MelAvatar3D size={36} />
        </span>
        <span className="chat-header__badge">
          <MelAvatar3D size={42} />
        </span>
        <div className="chat-header__copy">
          <h1>
            <span className="chat-header__desktop-title">Mel — Atendimento Empório da Música</span>
            <span className="chat-header__mobile-title">Mel — Empório da Música</span>
          </h1>
          {isDemo ? (
            <p title="Modo demonstrativo: respostas fictícias, sem o agente real.">
              <span className="status-dot status-dot--demo" />
              <span className="chat-header__desktop-status">Modo demonstração</span>
              <span className="chat-header__mobile-status">Demonstração</span>
            </p>
          ) : (
            <p title={health?.detail || HEALTH_TITLES[healthStatus]}>
              <span className={`status-dot ${healthLabel.dot}`.trim()} />
              <span className="chat-header__desktop-status">{healthLabel.desktop}</span>
              <span className="chat-header__mobile-status">{healthLabel.mobile}</span>
            </p>
          )}
        </div>
        <button type="button" className="chat-header__menu" onClick={onOpenSidebar} aria-label="Abrir histórico">
          <IconMenu />
        </button>
      </header>

      <MessageList
        messages={conversation.messages}
        animation={conversation.animation}
        isSending={isSending}
        error={error}
        onRetry={canRetry ? onRetry : undefined}
        onDismissError={onDismissError}
        onOpenProduct={onOpenProduct}
        onSuggestion={onSend}
        showSuggestions={userTurns === 0}
      />

      <div className="chat-dock">
        <Composer key={conversation.id} disabled={isSending} onSend={onSend} />
        {isDemo ? (
          <p className="privacy-note">
            Modo demonstração: respostas fictícias, sem conexão com o agente.
          </p>
        ) : (
          <p className="privacy-note">As conversas ficam salvas neste navegador.</p>
        )}
      </div>
    </section>
  )
}
