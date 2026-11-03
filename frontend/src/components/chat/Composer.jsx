import { useState } from 'react'
import { IconClip, IconSend, IconSmile } from '../icons.jsx'

/** Limite da API (POST /api/chat): 1..2000 caracteres. */
const MAX_MESSAGE_LENGTH = 2000
const COUNTER_FROM = MAX_MESSAGE_LENGTH - 200

export default function Composer({ disabled, onSend }) {
  const [value, setValue] = useState('')

  function submit() {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <button
        type="button"
        className="composer__icon composer__icon--emoji"
        title="Emojis"
        aria-label="Inserir emoji"
        onClick={() => setValue((prev) => `${prev}🎸 `.slice(0, MAX_MESSAGE_LENGTH))}
      >
        <IconSmile />
      </button>
      <button type="button" className="composer__icon" disabled title="Anexos ainda não estão disponíveis" aria-label="Anexar arquivo">
        <IconClip />
      </button>
      <textarea
        rows={1}
        value={value}
        placeholder="Digite sua mensagem..."
        maxLength={MAX_MESSAGE_LENGTH}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
      />
      {value.length >= COUNTER_FROM ? (
        <span
          className={`composer__count${value.length >= MAX_MESSAGE_LENGTH ? ' composer__count--full' : ''}`}
          aria-live="polite"
          title={`Limite de ${MAX_MESSAGE_LENGTH} caracteres por mensagem`}
        >
          {value.length}/{MAX_MESSAGE_LENGTH}
        </span>
      ) : null}
      <button type="submit" className="composer__send" disabled={disabled || !value.trim()} aria-label="Enviar">
        <IconSend />
      </button>
    </form>
  )
}
