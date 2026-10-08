import { createContext, useContext } from 'react'
import type { Node } from '@xyflow/react'
import type { NodeTypeDef } from '../types'

export type FlowNodeData = {
  nodeType: string
  config: Record<string, unknown>
  hasError?: boolean
}

export type FlowNode = Node<FlowNodeData, 'flow'>

export const CATEGORY_META: Record<NodeTypeDef['category'], { label: string; color: string }> = {
  trigger: { label: 'Gatilho', color: 'var(--trigger)' },
  action: { label: 'Ação', color: 'var(--action)' },
  condition: { label: 'Condição', color: 'var(--condition)' },
}

export const CatalogContext = createContext<Record<string, NodeTypeDef>>({})

export function useCatalog() {
  return useContext(CatalogContext)
}

export function defaultConfig(def: NodeTypeDef): Record<string, unknown> {
  const config: Record<string, unknown> = {}
  for (const field of def.fields) {
    if (field.default !== undefined) config[field.name] = field.default
  }
  return config
}

function shorten(value: unknown, max = 90): string {
  const text = String(value ?? '').trim()
  return text.length > max ? `${text.slice(0, max)}…` : text
}

/** Resumo exibido no corpo do nó no canvas. */
export function summarize(def: NodeTypeDef | undefined, config: Record<string, unknown>): string {
  if (!def) return 'Tipo desconhecido'
  switch (def.type) {
    case 'trigger.comment_received':
      return config.media_id ? `Somente na publicação ${config.media_id}` : 'Qualquer publicação'
    case 'trigger.message_received':
      return 'Qualquer DM recebida'
    case 'action.delay': {
      const s = Number(config.seconds || 0)
      return s >= 3600 ? `${(s / 3600).toFixed(1)} h` : s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`
    }
    case 'action.ai':
      return shorten(config.instructions) || 'Configure as instruções'
    case 'action.set_variable':
      return config.name ? `vars.${config.name} ${config.mode === 'append' ? '+=' : '='} ${shorten(config.value, 50)}` : 'Configure a variável'
    case 'condition.check': {
      const op = def.fields.find((f) => f.name === 'operator')?.options?.find((o) => o.value === config.operator)
      return `${shorten(config.left, 30)} ${op?.label ?? ''} ${shorten(config.value, 30)}`.trim()
    }
    case 'action.end':
      return ''
    default:
      return shorten(config.text) || 'Configure o texto'
  }
}
