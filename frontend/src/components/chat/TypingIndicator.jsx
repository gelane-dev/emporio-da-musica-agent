import MelAvatar from '../../assets/mel/MelAvatar.jsx'

export default function TypingIndicator() {
  return (
    <div className="msg msg--assistant" aria-live="polite" aria-label="Assistente está respondendo">
      <span className="msg__avatar" aria-hidden="true">
        <MelAvatar size={30} />
      </span>
      <div className="typing">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}
