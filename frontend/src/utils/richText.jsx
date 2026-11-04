/**
 * Negrito em Markdown (`**texto**`) nas respostas da Mel, como elementos React.
 *
 * Só o negrito: o resto do texto continua como está (quebras de linha mantidas pelo CSS
 * `white-space: pre-wrap`, listas com "- " legíveis como texto). Nada vira HTML bruto, então
 * não há como o texto da resposta injetar marcação na página.
 */
const BOLD = /\*\*([^*\n]+?)\*\*/g

export function renderInlineMarkdown(text) {
  if (!text || !text.includes('**')) return text
  const parts = []
  let last = 0
  for (const match of text.matchAll(BOLD)) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    parts.push(<strong key={match.index}>{match[1]}</strong>)
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}
