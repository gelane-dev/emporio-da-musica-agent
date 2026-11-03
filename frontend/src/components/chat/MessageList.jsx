import { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble.jsx'
import SuggestionChips from './SuggestionChips.jsx'
import TypingIndicator from './TypingIndicator.jsx'

export default function MessageList({
  messages,
  isSending,
  error,
  onRetry,
  onDismissError,
  onOpenProduct,
  onSuggestion,
  showSuggestions,
}) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isSending, error])

  return (
    <div className="transcript" aria-live="polite">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} onOpenProduct={onOpenProduct} />
      ))}
      {isSending ? <TypingIndicator /> : null}
      {error ? (
        <div className="chat-error" role="alert">
          <p>{error}</p>
          <div className="chat-error__actions">
            {onRetry ? (
              <button type="button" onClick={onRetry}>
                Tentar de novo
              </button>
            ) : null}
            <button type="button" onClick={onDismissError}>
              Fechar
            </button>
          </div>
        </div>
      ) : null}
      <SuggestionChips visible={showSuggestions && !isSending} onPick={onSuggestion} />
      <div ref={endRef} />
    </div>
  )
}
