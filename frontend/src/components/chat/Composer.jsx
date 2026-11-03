import { useState } from 'react'
import { IconClip, IconSend, IconSmile } from '../icons.jsx'

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
        onClick={() => setValue((prev) => `${prev}🎸 `)}
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
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        disabled={disabled}
      />
      <button type="submit" className="composer__send" disabled={disabled || !value.trim()} aria-label="Enviar">
        <IconSend />
      </button>
    </form>
  )
}
