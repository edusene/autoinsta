const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
const timeOnly = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTime.format(new Date(value)) : '—'
}

export function formatTime(value: string | null | undefined): string {
  return value ? timeOnly.format(new Date(value)) : '—'
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${Math.round(ms / 60_000)} min`
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return 'nunca'
  const seconds = Math.round((Date.now() - new Date(value).getTime()) / 1000)
  if (seconds < 60) return 'agora'
  if (seconds < 3600) return `há ${Math.floor(seconds / 60)} min`
  if (seconds < 86400) return `há ${Math.floor(seconds / 3600)} h`
  return `há ${Math.floor(seconds / 86400)} d`
}

export const TRIGGER_LABELS: Record<string, string> = {
  'trigger.message_received': 'Mensagem recebida',
  'trigger.comment_received': 'Comentário recebido',
}
