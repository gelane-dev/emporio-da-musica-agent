import { ClefMark, IconDotsVertical, IconHeadset, IconLock, IconMenu, IconUser } from '../icons.jsx'
import Composer from './Composer.jsx'
import MessageList from './MessageList.jsx'

export default function ChatPanel({
  conversation,
  isDemo,
  isSending,
  error,
  onSend,
  onOpenProduct,
  onOpenSidebar,
  onDismissError,
  onRetry,
}) {
  const userTurns = conversation.messages.filter((item) => item.role === 'user').length

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <span className="chat-header__mark chat-header__mark--mobile">
          <ClefMark size={34} />
        </span>
        <span className="chat-header__badge">
          <IconHeadset />
        </span>
        <div className="chat-header__copy">
          <h1>
            <span className="chat-header__desktop-title">Atendimento Empório da Música</span>
            <span className="chat-header__mobile-title">Empório da Música</span>
          </h1>
          {isDemo ? (
            <p title="Modo demonstrativo: respostas fictícias, sem o agente real.">
              <span className="status-dot status-dot--demo" />
              <span className="chat-header__desktop-status">Modo demonstração</span>
              <span className="chat-header__mobile-status">Demonstração</span>
            </p>
          ) : (
            <p>
              <span className="status-dot" />
              <span className="chat-header__desktop-status">Online</span>
              <span className="chat-header__mobile-status">AI Assistant</span>
            </p>
          )}
        </div>
        <div className="chat-header__actions">
          <button type="button" className="chat-header__action" aria-label="Perfil do usuário" title="Perfil">
            <IconUser />
          </button>
          <button type="button" className="chat-header__action" aria-label="Mais opções" title="Opções">
            <IconDotsVertical />
          </button>
        </div>
        <button type="button" className="chat-header__menu" onClick={onOpenSidebar} aria-label="Abrir histórico">
          <IconMenu />
        </button>
      </header>

      <MessageList
        messages={conversation.messages}
        isSending={isSending}
        error={error}
        onRetry={onRetry}
        onDismissError={onDismissError}
        onOpenProduct={onOpenProduct}
        onSuggestion={onSend}
        showSuggestions={userTurns === 0}
      />

      <div className="chat-dock">
        <Composer disabled={isSending} onSend={onSend} />
        {isDemo ? (
          <p className="privacy-note">
            Modo demonstração: respostas fictícias, sem conexão com o agente.
          </p>
        ) : (
          <p className="privacy-note">
            <IconLock /> Suas mensagens são privadas e seguras.
          </p>
        )}
      </div>
    </section>
  )
}
