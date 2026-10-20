import { useState, type ReactNode } from 'react'
import type { ExecutionStatus, WorkflowStatus } from '../types'

export function Loading() {
  return (
    <div className="center">
      <div className="spinner" />
    </div>
  )
}

export function ErrorAlert({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null
  return (
    <div className="alert alert-error row">
      <span>{message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry} style={{ marginLeft: 'auto' }}>
          Tentar novamente
        </button>
      )}
    </div>
  )
}

const WORKFLOW_STATUS: Record<WorkflowStatus, [string, string]> = {
  draft: ['Rascunho', ''],
  active: ['Ativo', 'badge-success'],
  inactive: ['Inativo', 'badge-warning'],
}

export function WorkflowStatusBadge({ status }: { status: WorkflowStatus }) {
  const [label, cls] = WORKFLOW_STATUS[status]
  return <span className={`badge ${cls}`}>{label}</span>
}

const EXECUTION_STATUS: Record<ExecutionStatus, [string, string]> = {
  running: ['Executando', 'badge-info'],
  waiting: ['Aguardando', 'badge-info'],
  success: ['Sucesso', 'badge-success'],
  error: ['Erro', 'badge-danger'],
  cancelled: ['Cancelada', 'badge-warning'],
}

export function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  const [label, cls] = EXECUTION_STATUS[status]
  return <span className={`badge ${cls}`}>{label}</span>
}

/** Botão com confirmação embutida (sem window.confirm). */
export function ConfirmButton({
  children,
  confirmLabel = 'Confirmar',
  onConfirm,
  className = 'btn btn-danger',
  disabled,
}: {
  children: ReactNode
  confirmLabel?: string
  onConfirm: () => void | Promise<void>
  className?: string
  disabled?: boolean
}) {
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  if (!asking) {
    return (
      <button className={className} onClick={() => setAsking(true)} disabled={disabled}>
        {children}
      </button>
    )
  }
  return (
    <span className="row" style={{ gap: 6 }}>
      <button
        className="btn btn-danger-solid btn-sm"
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onConfirm()
          } finally {
            setBusy(false)
            setAsking(false)
          }
        }}
      >
        {confirmLabel}
      </button>
      <button className="btn btn-sm" onClick={() => setAsking(false)} disabled={busy}>
        Cancelar
      </button>
    </span>
  )
}

const TAG_RE = /^[\p{L}\p{N}_\- ]{1,40}$/u

/** Campo de tags: Enter ou vírgula adiciona; × remove. Tags ficam em minúsculas. */
export function TagInput({
  value,
  onChange,
  suggestions = [],
  placeholder = 'Adicionar tag…',
}: {
  value: string[]
  onChange: (tags: string[]) => void
  suggestions?: string[]
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')
  const listId = `tags-${suggestions.length}`
  const add = (raw: string) => {
    const tag = raw.trim().toLowerCase()
    if (tag && TAG_RE.test(tag) && !value.includes(tag)) onChange([...value, tag])
    setDraft('')
  }
  return (
    <div className="tag-input">
      {value.map((tag) => (
        <span key={tag} className="tag">
          {tag}
          <button type="button" aria-label={`Remover ${tag}`} onClick={() => onChange(value.filter((t) => t !== tag))}>×</button>
        </span>
      ))}
      <input
        value={draft}
        list={suggestions.length ? listId : undefined}
        placeholder={value.length ? '' : placeholder}
        maxLength={40}
        onChange={(e) => (e.target.value.endsWith(',') ? add(e.target.value.slice(0, -1)) : setDraft(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            add(draft)
          } else if (e.key === 'Backspace' && !draft && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => draft && add(draft)}
      />
      {suggestions.length > 0 && (
        <datalist id={listId}>
          {suggestions.filter((s) => !value.includes(s)).map((s) => <option key={s} value={s} />)}
        </datalist>
      )}
    </div>
  )
}

export function Tags({ tags }: { tags: string[] }) {
  if (!tags.length) return null
  return (
    <span className="tags">
      {tags.map((t) => <span key={t} className="tag tag-sm">{t}</span>)}
    </span>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  )
}
