import { useCallback, useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../lib/api'

/** Intervalo padrão da atualização automática das telas do painel. */
export const AUTO_REFRESH_MS = 10_000

interface Options {
  /** Recarrega automaticamente a cada N ms (pausa com a aba em segundo plano). */
  refreshMs?: number
}

/** Carrega um recurso GET da API, com estados de loading/erro, reload manual e atualização automática opcional. */
export function useApi<T>(path: string | null, { refreshMs }: Options = {}) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const inFlight = useRef(false)

  // silent: atualização em segundo plano, sem spinner e sem apagar o que está na tela
  const fetchData = useCallback(async (silent: boolean) => {
    if (!path || inFlight.current) return
    inFlight.current = true
    if (!silent) {
      setLoading(true)
      setError(null)
    }
    try {
      setData(await api.get<T>(path))
      if (silent) setError(null)
    } catch (err) {
      // Falha momentânea na atualização automática não substitui dados válidos na tela
      if (!silent) setError(errorMessage(err))
    } finally {
      inFlight.current = false
      if (!silent) setLoading(false)
    }
  }, [path])

  const load = useCallback(() => fetchData(false), [fetchData])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!refreshMs || !path) return
    const refresh = () => {
      if (document.visibilityState === 'visible') fetchData(true)
    }
    const timer = window.setInterval(refresh, refreshMs)
    // Ao voltar para a aba, atualiza na hora
    document.addEventListener('visibilitychange', refresh)
    window.addEventListener('focus', refresh)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refresh)
      window.removeEventListener('focus', refresh)
    }
  }, [refreshMs, path, fetchData])

  return { data, setData, error, loading, reload: load }
}
