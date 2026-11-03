import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createConversation, seedConversations } from '../data/demo.js'
import { ApiError } from '../services/http.js'
import { createSession, isDemoMode, sendChatMessage } from '../services/chatService.js'

const DEMO_MODE = isDemoMode()

// Chaves separadas por modo: conversas demonstrativas e reais não se misturam.
const STORAGE_KEY = DEMO_MODE ? 'emporio.conversations.v1' : 'emporio.conversations.api.v1'

const SESSION_LOST_NOTICE =
  'O atendimento foi reiniciado e o contexto anterior desta conversa se perdeu. ' +
  'Sua última mensagem foi reenviada em um novo atendimento — se precisar, repita detalhes já informados.'

const ERROR_MESSAGES = {
  session_busy: 'Ainda estou respondendo à sua mensagem anterior. Aguarde um instante e tente de novo.',
  agent_unavailable:
    'O atendimento está indisponível no momento (o agente não pôde ser iniciado). Tente novamente mais tarde.',
}

function friendlyError(err, fallback) {
  if (err instanceof ApiError && ERROR_MESSAGES[err.code]) return ERROR_MESSAGES[err.code]
  return err?.message || fallback
}

function isSessionLost(err) {
  return err instanceof ApiError && err.status === 404 && err.code === 'session_not_found'
}

function newConversation() {
  const conversation = createConversation()
  // No modo API a saudação vem do backend (POST /api/sessions), não do texto demonstrativo.
  return DEMO_MODE ? conversation : { ...conversation, messages: [], sessionId: null }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.conversations?.length) return null
    return parsed
  } catch {
    return null
  }
}

function persist(state) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      conversations: state.conversations,
      activeId: state.activeId,
    }),
  )
}

function initialState() {
  const stored = loadState()
  if (stored) return stored
  const conversations = DEMO_MODE ? seedConversations() : [newConversation()]
  return { conversations, activeId: conversations[0].id }
}

function updateConversation(state, conversationId, updater) {
  return {
    ...state,
    conversations: state.conversations.map((item) => (item.id === conversationId ? updater(item) : item)),
  }
}

function makeMessage(role, text, extra = {}) {
  return {
    id: `msg-${crypto.randomUUID()}`,
    role,
    text,
    createdAt: new Date().toISOString(),
    ...extra,
  }
}

export function useConversations() {
  const [state, setState] = useState(initialState)
  const { conversations, activeId } = state
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const sendingRef = useRef(false)
  const lastTextRef = useRef('')
  const stateRef = useRef(state)
  const greetingRequests = useRef(new Map())

  const active = useMemo(
    () => conversations.find((item) => item.id === activeId) ?? conversations[0],
    [conversations, activeId],
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return conversations
    return conversations.filter((item) => {
      const haystack = [item.title, ...item.messages.map((message) => message.text)].join(' ').toLowerCase()
      return haystack.includes(needle)
    })
  }, [conversations, query])

  const commit = useCallback((updater) => {
    setState((current) => {
      const next = updater(current)
      stateRef.current = next
      persist(next)
      return next
    })
  }, [])

  const findConversation = useCallback(
    (conversationId) => stateRef.current.conversations.find((item) => item.id === conversationId),
    [],
  )

  const selectConversation = useCallback(
    (id) => {
      setError('')
      commit((current) => ({ ...current, activeId: id }))
    },
    [commit],
  )

  /** Modo API: abre a sessão no backend e mostra a saudação real da Mel. */
  const requestGreeting = useCallback(
    (conversationId) => {
      const pending = greetingRequests.current.get(conversationId)
      if (pending) return pending

      const run = (async () => {
        sendingRef.current = true
        setIsSending(true)
        setError('')
        try {
          const session = await createSession()
          commit((current) =>
            updateConversation(current, conversationId, (item) => {
              // Se uma mensagem já abriu outra sessão nesse meio-tempo, mantém a existente.
              if (item.sessionId || item.messages.length > 0) return item
              const greeting = makeMessage('assistant', session.greeting, { createdAt: session.createdAt })
              return {
                ...item,
                sessionId: session.sessionId,
                updatedAt: greeting.createdAt,
                messages: session.greeting ? [greeting] : [],
              }
            }),
          )
        } catch (err) {
          setError(
            `Não foi possível iniciar o atendimento. ${friendlyError(err, 'Tente novamente em instantes.')}`,
          )
        } finally {
          sendingRef.current = false
          setIsSending(false)
          greetingRequests.current.delete(conversationId)
        }
      })()
      greetingRequests.current.set(conversationId, run)
      return run
    },
    [commit],
  )

  const activeNeedsGreeting =
    !DEMO_MODE && Boolean(active) && active.messages.length === 0 && !active.sessionId
  const activeConversationId = active?.id

  useEffect(() => {
    if (activeNeedsGreeting && activeConversationId) void requestGreeting(activeConversationId)
  }, [activeNeedsGreeting, activeConversationId, requestGreeting])

  const requestReply = useCallback(
    async (conversationId, text, history) => {
      sendingRef.current = true
      setIsSending(true)
      setError('')
      lastTextRef.current = text

      const send = (sessionId) => sendChatMessage({ sessionId, conversationId, message: text, history })

      try {
        let reply
        try {
          reply = await send(findConversation(conversationId)?.sessionId ?? null)
        } catch (err) {
          if (!isSessionLost(err)) throw err
          // Sessões vivem só na memória do servidor: após um reinício o id antigo deixa de existir.
          // Descarta o id, avisa o usuário e reenvia uma única vez numa sessão nova.
          commit((current) =>
            updateConversation(current, conversationId, (item) => ({
              ...item,
              sessionId: null,
              messages: [...item.messages, makeMessage('notice', SESSION_LOST_NOTICE)],
            })),
          )
          reply = await send(null)
        }

        const assistantText = (reply?.text ?? '').trim()
        const products = Array.isArray(reply?.products) ? reply.products : []
        if (!assistantText && products.length === 0) {
          setError('O assistente não retornou conteúdo para esta mensagem.')
          return
        }
        const assistantMessage = makeMessage('assistant', assistantText, {
          products,
          ...(reply?.stop ? { stop: reply.stop } : {}),
        })
        commit((current) =>
          updateConversation(current, conversationId, (item) => ({
            ...item,
            ...(reply?.sessionId ? { sessionId: reply.sessionId } : {}),
            updatedAt: assistantMessage.createdAt,
            messages: [...item.messages, assistantMessage],
          })),
        )
      } catch (err) {
        setError(friendlyError(err, 'Não foi possível concluir o atendimento.'))
      } finally {
        sendingRef.current = false
        setIsSending(false)
      }
    },
    [commit, findConversation],
  )

  const sendMessage = useCallback(
    async (rawText, targetId) => {
      const text = rawText.trim()
      if (!text || sendingRef.current) return

      const conversationId = targetId ?? activeId
      const userMessage = makeMessage('user', text)

      let history = []
      commit((current) => {
        const found = current.conversations.find((item) => item.id === conversationId)
        if (!found) {
          const created = newConversation()
          created.id = conversationId
          created.title = text.slice(0, 42)
          created.updatedAt = userMessage.createdAt
          created.messages = [...created.messages, userMessage]
          history = created.messages
          return {
            activeId: conversationId,
            conversations: [created, ...current.conversations],
          }
        }
        const titled = found.title === 'Nova conversa' ? text.slice(0, 42) : found.title
        const nextItem = {
          ...found,
          title: titled,
          updatedAt: userMessage.createdAt,
          messages: [...found.messages, userMessage],
        }
        history = nextItem.messages
        return {
          ...current,
          activeId: conversationId,
          conversations: current.conversations.map((item) => (item.id === conversationId ? nextItem : item)),
        }
      })

      await requestReply(conversationId, text, history)
    },
    [activeId, commit, requestReply],
  )

  const startConversation = useCallback(
    (seedMessage) => {
      const conversation = newConversation()
      setError('')
      commit((current) => ({
        conversations: [conversation, ...current.conversations],
        activeId: conversation.id,
      }))
      if (seedMessage) {
        if (DEMO_MODE) {
          void sendMessage(seedMessage, conversation.id)
        } else {
          // Saudação primeiro; se ela falhar, a mensagem segue e o backend cria a sessão.
          void requestGreeting(conversation.id).then(() => sendMessage(seedMessage, conversation.id))
        }
      }
      return conversation.id
    },
    [commit, requestGreeting, sendMessage],
  )

  const retryLast = useCallback(() => {
    if (sendingRef.current || !active) return
    if (!DEMO_MODE && active.messages.length === 0 && !active.sessionId) {
      void requestGreeting(active.id)
      return
    }
    const text = lastTextRef.current.trim()
    if (!text) return
    // Avisos (role "notice") não contam: a última mensagem real decide se é só reenviar.
    const last = active.messages.findLast((item) => item.role !== 'notice')
    if (last?.role === 'user' && last.text === text) {
      void requestReply(active.id, text, active.messages)
      return
    }
    void sendMessage(text)
  }, [active, requestGreeting, requestReply, sendMessage])

  return {
    conversations: filtered,
    active,
    isDemo: DEMO_MODE,
    isSending,
    error,
    query,
    setQuery,
    setError,
    selectConversation,
    startConversation,
    sendMessage,
    retryLast,
  }
}
