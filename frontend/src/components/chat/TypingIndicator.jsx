import { GuitarMark } from '../icons.jsx'

export default function TypingIndicator() {
  return (
    <div className="msg msg--assistant" aria-live="polite" aria-label="Assistente está respondendo">
      <span className="msg__avatar" aria-hidden="true">
        <GuitarMark size={18} />
      </span>
      <div className="typing">
        <span />
        <span />
        <span />
      </div>
    </div>
  )
}
