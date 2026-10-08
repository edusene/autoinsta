import { supabase } from './supabase'

// Vazio = mesma origem (o Vite faz proxy de /api em desenvolvimento).
export const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) || '').replace(/\/$/, '')

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message)
    this.code = code
    this.status = status
    this.details = details
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const headers: Record<string, string> = {}
  if (data.session) headers.Authorization = `Bearer ${data.session.access_token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Não foi possível conectar ao servidor.', 'NETWORK_ERROR', 0)
  }

  const json = await res.json().catch(() => null)
  if (!res.ok || !json?.success) {
    const err = json?.error ?? {}
    if (res.status === 401) await supabase.auth.signOut()
    throw new ApiError(err.message || `Erro ${res.status}`, err.code || 'HTTP_ERROR', res.status, err.details)
  }
  return json.data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Erro inesperado.'
}
