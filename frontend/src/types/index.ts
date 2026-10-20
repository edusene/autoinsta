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
  /** Mensagens enviadas com link rastreado ou botão / quantas tiveram clique (CTR) */
  trackable_count: number
  clicked_count: number
}

export interface Workflow extends Omit<WorkflowSummary, 'executions_count' | 'errors_count' | 'trackable_count' | 'clicked_count'> {
  graph: Graph
}

export interface FlowButton {
  id: string
  title: string
  type: 'reply' | 'url'
  url?: string
}

export interface FieldDef {
  name: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'buttons'
  required?: boolean
  default?: unknown
  help?: string
  max_length?: number
  min?: number
  max?: number
  step?: number
  options?: { value: string; label: string }[]
  /** Mostra o campo só quando outro campo tem o valor indicado */
  show_if?: { field: string; equals: unknown }
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
  /** "buttons": cada botão de resposta vira uma saída do nó */
  dynamic_outputs?: 'buttons'
}

/** Envios e cliques de um nó (CTR) */
export interface NodeStats {
  sent: number
  trackable: number
  clicked: number
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

export type ContactStatus = 'active' | 'blocked' | 'archived'

export interface Contact {
  id: string
  ig_scoped_id: string
  username: string | null
  name: string | null
  status: ContactStatus
  tags: string[]
  notes: string | null
  automation_paused: boolean
  last_interaction_at: string | null
  last_event_type: string | null
  last_inbound_at: string | null
  unread_count: number
  /** Dentro da janela de 24h da Meta (pode receber DM) */
  can_message: boolean
  created_at: string
}

export interface ContactDetail extends Contact {
  window_expires_at: string | null
  events: { id: string; event_type: string; summary: string | null; created_at: string }[]
}

export interface TagCount {
  tag: string
  count: number
}

export interface Conversation {
  id: string
  username: string | null
  name: string | null
  tags: string[]
  status: ContactStatus
  automation_paused: boolean
  last_message_at: string
  last_message_preview: string | null
  unread_count: number
  can_message: boolean
}

export interface InboxMessage {
  id: string
  direction: 'in' | 'out'
  source: 'contact' | 'workflow' | 'inbox' | 'broadcast' | 'instagram_app'
  kind: string
  text: string | null
  buttons: FlowButton[]
  status: 'received' | 'sending' | 'sent' | 'failed'
  error: string | null
  workflow_id: string | null
  broadcast_id: string | null
  trackable: boolean
  clicked_at: string | null
  created_at: string
}

export interface ConversationDetail {
  contact: ContactDetail
  messages: InboxMessage[]
}

export interface CtrStats {
  sent: number
  trackable: number
  clicked: number
}

export type BroadcastStatus = 'draft' | 'scheduled' | 'sending' | 'done' | 'cancelled' | 'failed'

export interface Broadcast {
  id: string
  name: string
  text: string
  buttons: FlowButton[]
  audience: { tags?: string[] }
  track_links: boolean
  status: BroadcastStatus
  scheduled_at: string | null
  started_at: string | null
  finished_at: string | null
  last_error: string | null
  created_at: string
  total_count: number
  sent_count: number
  skipped_count: number
  failed_count: number
  pending_count: number
  trackable_count: number
  clicked_count: number
}

export interface BroadcastRecipient {
  id: number
  contact_id: string
  username: string | null
  name: string | null
  status: 'pending' | 'processing' | 'sent' | 'skipped' | 'failed'
  reason: string | null
  processed_at: string | null
  clicked_at: string | null
}

export interface Dashboard {
  instagram: InstagramStatus
  workflows: { total: number; active: number }
  executions_24h: { total: number; success: number; errors: number; in_progress: number }
  contacts_count: number
  ctr_7d: CtrStats
  top_links: { url: string; sent: number; clicked: number; clicks: number }[]
  unread_conversations: number
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
