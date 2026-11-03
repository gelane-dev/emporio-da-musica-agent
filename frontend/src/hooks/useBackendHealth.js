import { useEffect, useState } from 'react'
import { checkHealth, isDemoMode } from '../services/chatService.js'

/**
 * Estado do backend para o indicador do cabeçalho, consultado uma vez ao montar a página.
 * `status`: 'demo' | 'checking' | 'online' | 'degraded' | 'offline'.
 */
export function useBackendHealth() {
  const [health, setHealth] = useState(() => ({
    status: isDemoMode() ? 'demo' : 'checking',
    detail: null,
  }))

  useEffect(() => {
    if (isDemoMode()) return undefined
    let cancelled = false
    checkHealth()
      .then((payload) => {
        if (cancelled) return
        const ready = payload?.status === 'ok' && payload?.agent_ready !== false
        setHealth({ status: ready ? 'online' : 'degraded', detail: payload?.detail ?? null })
      })
      .catch(() => {
        if (!cancelled) setHealth({ status: 'offline', detail: null })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return health
}
