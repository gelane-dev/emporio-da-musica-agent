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
  session_busy:
    'Ainda estou respondendo à sua mensagem anterior. Aguarde alguns segundos e tente de novo.',
  agent_unavailable:
    'O atendimento está indisponível no momento (o agente não pôde ser iniciado). Tente novamente mais tarde.',
}

const CHAT_TIMEOUT_MESSAGE =
  'A resposta está demorando mais que o normal e ainda pode estar sendo processada. ' +
  'Aguarde alguns segundos antes de usar "Tentar de novo" — isso pode enviar a mesma pergunta outra vez.'

const BUSY_LOCAL_MESSAGE =
  'Sua mensagem não foi enviada porque a resposta anterior desta conversa ainda está em andamento. ' +
  'Quando ela chegar, use "Tentar de novo" para enviá-la.'

/** Esperas entre novas tentativas automáticas quando a API responde 409 session_busy. */
const BUSY_RETRY_DELAYS_MS = [2000, 3500, 5000]

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function friendlyError(err, fallback) {
  if (err instanceof ApiError && ERROR_MESSAGES[err.code]) return ERROR_MESSAGES[err.code]
  return err?.message || fallback
}

function isSessionLost(err) {
  return err instanceof ApiError && err.status === 404 && err.code === 'session_not_found'
}

function isSessionBusy(err) {
  return err instanceof ApiError && err.status === 409 && err.code === 'session_busy'
}

function isInvalidRequest(err) {
  return err instanceof ApiError && err.status === 422
}

// Conversa no limite de mensagens (429 session_full): reenviar falharia de novo; o caminho é uma conversa nova.
function isSessionFull(err) {
  return err instanceof ApiError && err.status === 429 && err.code === 'session_full'
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
  const [query, setQuery] = useState('')
  // Envio, erro e última mensagem são POR CONVERSA: uma conversa nunca bloqueia,
  // esconde o indicador de digitação nem mostra o erro de outra.
  const [pending, setPending] = useState(() => new Set())
  const [errors, setErrors] = useState(() => new Map())
  const pendingRef = useRef(new Set())
  const lastTextRef = useRef(new Map())
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

  const setPendingFor = useCallback((conversationId, isPending) => {
    const next = new Set(pendingRef.current)
    if (isPending) next.add(conversationId)
    else next.delete(conversationId)
    pendingRef.current = next
    setPending(next)
  }, [])

  /** Define (ou limpa, com mensagem vazia) o erro de uma conversa. */
  const setErrorFor = useCallback((conversationId, message, retryable = true) => {
    setErrors((current) => {
      const next = new Map(current)
      if (message) next.set(conversationId, { message, retryable })
      else next.delete(conversationId)
      return next
    })
  }, [])

  const selectConversation = useCallback(
    (id) => {
      commit((current) => ({ ...current, activeId: id }))
    },
    [commit],
  )

  /** Modo API: abre a sessão no backend e mostra a saudação real da Mel. */
  const requestGreeting = useCallback(
    (conversationId) => {
      const running = greetingRequests.current.get(conversationId)
      if (running) return running

      const run = (async () => {
        setPendingFor(conversationId, true)
        setErrorFor(conversationId, '')
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
          setErrorFor(
            conversationId,
            `Não foi possível iniciar o atendimento. ${friendlyError(err, 'Tente novamente em instantes.')}`,
          )
        } finally {
          setPendingFor(conversationId, false)
          greetingRequests.current.delete(conversationId)
        }
      })()
      greetingRequests.current.set(conversationId, run)
      return run
    },
    [commit, setErrorFor, setPendingFor],
  )

  const activeNeedsGreeting =
    !DEMO_MODE && Boolean(active) && active.messages.length === 0 && !active.sessionId
  const activeConversationId = active?.id

  useEffect(() => {
    if (activeNeedsGreeting && activeConversationId) void requestGreeting(activeConversationId)
  }, [activeNeedsGreeting, activeConversationId, requestGreeting])

  const requestReply = useCallback(
    async (conversationId, text) => {
      setPendingFor(conversationId, true)
      setErrorFor(conversationId, '')
      lastTextRef.current.set(conversationId, text)

      // 409 session_busy: o servidor ainda processa uma mensagem desta sessão (ex.: após um
      // timeout do cliente). Espera e tenta de novo algumas vezes antes de mostrar o erro.
      const send = async (sessionId) => {
        for (let attempt = 0; ; attempt += 1) {
          try {
            return await sendChatMessage({ sessionId, conversationId, message: text })
          } catch (err) {
            if (!isSessionBusy(err) || attempt >= BUSY_RETRY_DELAYS_MS.length) throw err
            await wait(BUSY_RETRY_DELAYS_MS[attempt])
          }
        }
      }

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
          setErrorFor(conversationId, 'O assistente não retornou conteúdo para esta mensagem.')
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
        const message =
          err instanceof ApiError && err.code === 'timeout'
            ? CHAT_TIMEOUT_MESSAGE
            : friendlyError(err, 'Não foi possível concluir o atendimento.')
        // 422 (mensagem inválida) e 429 session_full: reenviar falharia de novo, então não há retry.
        setErrorFor(conversationId, message, !isInvalidRequest(err) && !isSessionFull(err))
      } finally {
        setPendingFor(conversationId, false)
      }
    },
    [commit, findConversation, setErrorFor, setPendingFor],
  )

  /** Envia `rawText` na conversa `targetId` (padrão: a ativa). Devolve `false` se não enviou. */
  const sendMessage = useCallback(
    async (rawText, targetId) => {
      const text = rawText.trim()
      if (!text) return false

      const conversationId = targetId ?? stateRef.current.activeId
      if (pendingRef.current.has(conversationId)) {
        // Nunca descarta em silêncio: guarda o texto para o "Tentar de novo" e avisa.
        lastTextRef.current.set(conversationId, text)
        setErrorFor(conversationId, BUSY_LOCAL_MESSAGE)
        return false
      }
      const userMessage = makeMessage('user', text)

      commit((current) => {
        const found = current.conversations.find((item) => item.id === conversationId)
        if (!found) {
          const created = newConversation()
          created.id = conversationId
          created.title = text.slice(0, 42)
          created.updatedAt = userMessage.createdAt
          created.messages = [...created.messages, userMessage]
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
        return {
          ...current,
          activeId: conversationId,
          conversations: current.conversations.map((item) => (item.id === conversationId ? nextItem : item)),
        }
      })

      await requestReply(conversationId, text)
      return true
    },
    [commit, requestReply, setErrorFor],
  )

  const startConversation = useCallback(
    (seedMessage) => {
      const conversation = newConversation()
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
    if (!active || pendingRef.current.has(active.id)) return
    if (!DEMO_MODE && active.messages.length === 0 && !active.sessionId) {
      void requestGreeting(active.id)
      return
    }
    const text = (lastTextRef.current.get(active.id) ?? '').trim()
    if (!text) return
    // Avisos (role "notice") não contam: a última mensagem real decide se é só reenviar.
    const last = active.messages.findLast((item) => item.role !== 'notice')
    if (last?.role === 'user' && last.text === text) {
      void requestReply(active.id, text)
      return
    }
    void sendMessage(text, active.id)
  }, [active, requestGreeting, requestReply, sendMessage])

  const dismissError = useCallback(() => {
    if (active) setErrorFor(active.id, '')
  }, [active, setErrorFor])

  const activeError = active ? errors.get(active.id) : undefined

  return {
    conversations: filtered,
    active,
    isDemo: DEMO_MODE,
    isSending: Boolean(active) && pending.has(active.id),
    error: activeError?.message ?? '',
    canRetry: activeError?.retryable ?? false,
    query,
    setQuery,
    dismissError,
    selectConversation,
    startConversation,
    sendMessage,
    retryLast,
  }
}
