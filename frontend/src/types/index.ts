export type WorkflowStatus = 'draft' | 'active' | 'inactive'
export type ExecutionStatus = 'running' | 'waiting' | 'success' | 'error' | 'cancelled'

export interface GraphNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: { config: Record<string, unknown> }
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
}

export interface Graph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface WorkflowSummary {
  id: string
  name: string
  description: string | null
  status: WorkflowStatus
  trigger_type: string | null
  last_executed_at: string | null
  created_at: string
  updated_at: string
  executions_count: number
  errors_count: number
}

export interface Workflow extends Omit<WorkflowSummary, 'executions_count' | 'errors_count'> {
  graph: Graph
}

export interface FieldDef {
  name: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox'
  required?: boolean
  default?: unknown
  help?: string
  max_length?: number
  min?: number
  max?: number
  step?: number
  options?: { value: string; label: string }[]
}

export interface NodeTypeDef {
  type: string
  category: 'trigger' | 'action' | 'condition'
  label: string
  description: string
  outputs: string[]
  fields: FieldDef[]
  allowed_triggers?: string[]
  variables?: string[]
}

export interface ValidationIssue {
  node_id: string | null
  message: string
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  trigger_type: string | null
}

export interface InstagramStatus {
  connected: boolean
  status: 'connected' | 'disconnected' | 'token_expired' | 'error'
  account: null | {
    id: string
    username: string | null
    name: string | null
    account_type: string | null
    profile_picture_url: string | null
    webhook_subscribed: boolean
    last_webhook_at: string | null
    connected_at: string | null
    token_expires_at: string | null
    last_error: string | null
    connection_method: 'oauth' | 'server_token'
  }
  /** Formas de conexão disponíveis para o usuário logado (só em /api/instagram/*) */
  connect_options?: { oauth: boolean }
}

export interface DiagnosticCheck {
  key: string
  label: string
  status: 'ok' | 'warning' | 'error'
  detail: string
}

export interface ExecutionSummary {
  id: string
  workflow_id: string
  workflow_name: string
  contact_id: string | null
  trigger_type: string
  status: ExecutionStatus
  error: string | null
  steps_count: number
  started_at: string
  finished_at: string | null
  duration_ms: number
}

export interface ExecutionLog {
  id: number
  node_id: string | null
  node_type: string | null
  level: 'info' | 'warning' | 'error'
  message: string
  data: Record<string, unknown>
  created_at: string
}

export interface ExecutionDetail extends ExecutionSummary {
  trigger_event: Record<string, unknown>
  context: Record<string, unknown>
  current_node_id: string | null
  logs: ExecutionLog[]
}

export interface Paginated<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Contact {
  id: string
  ig_scoped_id: string
  username: string | null
  name: string | null
  status: string
  last_interaction_at: string | null
  last_event_type: string | null
  created_at: string
}

export interface ContactDetail extends Contact {
  events: { id: string; event_type: string; summary: string | null; created_at: string }[]
}

export interface Dashboard {
  instagram: InstagramStatus
  workflows: { total: number; active: number }
  executions_24h: { total: number; success: number; errors: number; in_progress: number }
  contacts_count: number
  recent_executions: ExecutionSummary[]
  recent_errors: ExecutionSummary[]
  openai_configured: boolean
}

export interface Settings {
  ai: {
    openai_configured: boolean
    key_hint: string | null
    platform_default_model: string
    default_model: string | null
  }
  instagram: InstagramStatus
}
