import { createContext, useContext } from 'react'
import type { Node } from '@xyflow/react'
import type { FlowButton, NodeStats, NodeTypeDef } from '../types'

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

/** Ações do editor usadas dentro dos nós e conexões (duplicar, remover, estatísticas). */
export interface EditorActions {
  duplicateNode: (id: string) => void
  deleteNode: (id: string) => void
  deleteEdge: (id: string) => void
  stats: Record<string, NodeStats>
}

export const EditorContext = createContext<EditorActions>({
  duplicateNode: () => {},
  deleteNode: () => {},
  deleteEdge: () => {},
  stats: {},
})

export function useEditor() {
  return useContext(EditorContext)
}

export function defaultConfig(def: NodeTypeDef): Record<string, unknown> {
  const config: Record<string, unknown> = {}
  for (const field of def.fields) {
    if (field.default !== undefined) config[field.name] = structuredClone(field.default)
  }
  return config
}

export function configButtons(config: Record<string, unknown>): FlowButton[] {
  return Array.isArray(config.buttons) ? (config.buttons as FlowButton[]) : []
}

/** Saídas do nó (igual ao backend): na mensagem com botões, cada botão de resposta é uma saída. */
export function nodeOutputs(def: NodeTypeDef | undefined, config: Record<string, unknown>): string[] {
  if (!def) return []
  if (def.dynamic_outputs === 'buttons') {
    const replies = configButtons(config).filter((b) => (b.type ?? 'reply') === 'reply' && b.id).map((b) => b.id)
    return replies.length ? [...replies, 'timeout'] : ['default']
  }
  return def.outputs
}

const OUTPUT_LABELS: Record<string, string> = { true: 'Sim', false: 'Não', replied: 'Respondeu', timeout: 'Sem resposta' }

export function outputLabel(def: NodeTypeDef | undefined, config: Record<string, unknown>, output: string): string {
  if (def?.dynamic_outputs === 'buttons') {
    if (output === 'timeout') return 'Sem clique'
    return configButtons(config).find((b) => b.id === output)?.title || 'Botão'
  }
  return OUTPUT_LABELS[output] ?? output
}

/** Cor da conexão conforme a saída de origem. */
export function outputColor(handle: string | null | undefined): string {
  if (handle === 'true' || handle === 'replied') return 'var(--success)'
  if (handle === 'false') return 'var(--danger)'
  if (handle === 'timeout') return 'var(--warning)'
  if (handle && handle !== 'default') return 'var(--action)'
  return 'var(--edge)'
}

function shorten(value: unknown, max = 90): string {
  const text = String(value ?? '').trim()
  return text.length > max ? `${text.slice(0, max)}…` : text
}

function minutes(value: unknown): string {
  const m = Number(value || 0)
  return m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? String(m % 60).padStart(2, '0') : ''}` : `${m} min`
}

/** Resumo exibido no corpo do nó no canvas. */
export function summarize(def: NodeTypeDef | undefined, config: Record<string, unknown>): string {
  if (!def) return 'Tipo desconhecido'
  switch (def.type) {
    case 'trigger.comment_received':
      return config.media_id ? `Somente na publicação ${config.media_id}` : 'Qualquer publicação'
    case 'trigger.message_received':
      return 'Qualquer DM recebida'
    case 'trigger.ig_me_link':
      return config.ref ? `ref = ${config.ref}` : 'Qualquer link ig.me'
    case 'trigger.new_contact':
    case 'trigger.story_mention':
    case 'trigger.story_reply':
    case 'trigger.message_reaction':
    case 'trigger.live_comment':
      return def.description.split('.')[0]
    case 'action.delay': {
      const s = Number(config.seconds || 0)
      return s >= 3600 ? `${(s / 3600).toFixed(1)} h` : s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`
    }
    case 'action.wait_reply':
      return `Espera até ${minutes(config.timeout_minutes)} pela resposta`
    case 'action.ai':
      return shorten(config.instructions) || 'Configure as instruções'
    case 'action.set_variable':
      return config.name ? `vars.${config.name} ${config.mode === 'append' ? '+=' : '='} ${shorten(config.value, 50)}` : 'Configure a variável'
    case 'action.add_tag':
      return config.tag ? `+ ${config.tag}` : 'Configure a tag'
    case 'action.remove_tag':
      return config.tag ? `− ${config.tag}` : 'Configure a tag'
    case 'condition.has_tag':
      return config.tag ? `Tem a tag “${config.tag}”?` : 'Configure a tag'
    case 'condition.follows':
      return 'Verifica se segue a conta'
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

const NODE_ICONS: Record<string, string> = {
  'trigger.message_received': 'message',
  'trigger.comment_received': 'comment',
  'trigger.new_contact': 'userPlus',
  'trigger.story_mention': 'at',
  'trigger.story_reply': 'story',
  'trigger.ig_me_link': 'link',
  'trigger.message_reaction': 'heart',
  'trigger.live_comment': 'live',
  'action.send_message': 'send',
  'action.send_buttons': 'buttons',
  'action.private_reply': 'reply',
  'action.reply_comment': 'megaphone',
  'action.delay': 'clock',
  'action.wait_reply': 'hourglass',
  'action.ai': 'sparkles',
  'action.set_variable': 'braces',
  'action.add_tag': 'tag',
  'action.remove_tag': 'tagOff',
  'action.end': 'stop',
  'condition.check': 'branch',
  'condition.follows': 'userCheck',
  'condition.has_tag': 'tag',
}

export function iconFor(nodeType: string): string {
  return NODE_ICONS[nodeType] ?? 'branch'
}
