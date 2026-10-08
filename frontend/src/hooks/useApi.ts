import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../lib/api'

/** Carrega um recurso GET da API, com estados de loading/erro e reload manual. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(path))

  const load = useCallback(async () => {
    if (!path) return
    setLoading(true)
    setError(null)
    try {
      setData(await api.get<T>(path))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    load()
  }, [load])

  return { data, setData, error, loading, reload: load }
}
