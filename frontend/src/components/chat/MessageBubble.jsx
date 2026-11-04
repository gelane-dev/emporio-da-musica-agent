import MelAvatar from '../../assets/mel/MelAvatar.jsx'
import ProductCard from '../products/ProductCard.jsx'
import { renderInlineMarkdown } from '../../utils/richText.jsx'
import { formatTime } from '../../utils/time.js'

export default function MessageBubble({ message, onOpenProduct }) {
  if (message.role === 'notice') {
    return (
      <p className="chat-notice" role="status">
        {message.text}
      </p>
    )
  }

  const isUser = message.role === 'user'
  return (
    <div className={`msg ${isUser ? 'msg--user' : 'msg--assistant'}`}>
      {!isUser ? (
        <span className="msg__avatar" aria-hidden="true">
          <MelAvatar size={30} />
        </span>
      ) : null}
      <div className="msg__stack">
        {message.text ? (
          <div className="msg__bubble">
            {/* Só as respostas da Mel têm negrito em Markdown; o texto do cliente fica literal. */}
            <p>{isUser ? message.text : renderInlineMarkdown(message.text)}</p>
          </div>
        ) : null}
        {message.products?.map((product) => (
          <ProductCard key={product.id} product={product} onOpen={onOpenProduct} />
        ))}
        <time className="msg__time" dateTime={message.createdAt}>
          {formatTime(message.createdAt)}
        </time>
      </div>
    </div>
  )
}
