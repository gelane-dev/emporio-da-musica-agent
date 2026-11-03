import { SUGGESTIONS } from '../../data/demo.js'

export default function SuggestionChips({ visible, onPick }) {
  if (!visible) return null
  return (
    <div className="suggestions">
      {SUGGESTIONS.map((item) => (
        <button type="button" key={item} onClick={() => onPick(item)}>
          {item}
        </button>
      ))}
    </div>
  )
}
