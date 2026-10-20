import {
  addEdge,
  Background,
  BackgroundVariant,
  ConnectionLineType,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type DragEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorAlert, Loading, WorkflowStatusBadge } from '../components/ui'
import { api, ApiError, errorMessage } from '../lib/api'
import { useTheme } from '../lib/theme'
import type { Graph, NodeStats, NodeTypeDef, ValidationResult, Workflow } from '../types'
import {
  CATEGORY_META, CatalogContext, defaultConfig, EditorContext, iconFor, nodeOutputs, type FlowNode,
} from './catalog'
import { Icon } from './Icon'
import { FlowEdge } from './FlowEdge'
import { FlowNodeView } from './FlowNodeView'
import { EditorHelp, NodeInspector } from './NodeInspector'

const nodeTypes = { flow: FlowNodeView }
const edgeTypes = { flow: FlowEdge }
const PALETTE_TITLES = { trigger: 'Gatilhos', condition: 'Condições', action: 'Ações' }
const defaultEdgeOptions = { type: 'flow' }
const DRAG_MIME = 'application/x-autoinsta-node'
const NODE_WIDTH = 260

function toFlow(graph: Graph): { nodes: FlowNode[]; edges: Edge[] } {
  return {
    nodes: graph.nodes.map((n) => ({
      id: n.id,
      type: 'flow',
      position: n.position,
      data: { nodeType: n.type, config: n.data?.config ?? {} },
    })),
    edges: graph.edges.map((e) => ({ ...e, sourceHandle: e.sourceHandle ?? null, ...defaultEdgeOptions })),
  }
}

function toGraph(nodes: FlowNode[], edges: Edge[]): Graph {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.data.nodeType,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      data: { config: n.data.config },
    })),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null })),
  }
}

function newId(type: string): string {
  return `${type.split('.')[1] ?? 'node'}-${Math.random().toString(36).slice(2, 8)}`
}

/** Organiza em camadas a partir do gatilho (cada nível abaixo do anterior, centralizado). */
function autoLayout(nodes: FlowNode[], edges: Edge[], byType: Record<string, NodeTypeDef>): FlowNode[] {
  const trigger = nodes.find((n) => byType[n.data.nodeType]?.category === 'trigger')
  const order = (e: Edge) => {
    const src = nodes.find((n) => n.id === e.source)
    const outputs = src ? nodeOutputs(byType[src.data.nodeType], src.data.config) : []
    return outputs.indexOf(e.sourceHandle ?? 'default')
  }
  const levels: string[][] = []
  const depth = new Map<string, number>()
  const queue = trigger ? [trigger.id] : []
  if (trigger) depth.set(trigger.id, 0)
  while (queue.length) {
    const id = queue.shift()!
    const d = depth.get(id)!
    ;(levels[d] ??= []).push(id)
    for (const e of edges.filter((x) => x.source === id).sort((a, b) => order(a) - order(b))) {
      if (!depth.has(e.target)) {
        depth.set(e.target, d + 1)
        queue.push(e.target)
      }
    }
  }
  const orphans = nodes.filter((n) => !depth.has(n.id)).map((n) => n.id)
  if (orphans.length) levels.push(orphans)

  const height = (id: string) => nodes.find((n) => n.id === id)?.measured?.height ?? 120
  const positions = new Map<string, { x: number; y: number }>()
  let y = 0
  for (const level of levels) {
    const gap = 60
    const width = level.length * NODE_WIDTH + (level.length - 1) * gap
    level.forEach((id, i) => positions.set(id, { x: i * (NODE_WIDTH + gap) - width / 2, y }))
    y += Math.max(...level.map(height)) + 90
  }
  return nodes.map((n) => ({ ...n, position: positions.get(n.id) ?? n.position }))
}

function Editor({ workflow, catalog }: { workflow: Workflow; catalog: NodeTypeDef[] }) {
  const byType = useMemo(() => Object.fromEntries(catalog.map((d) => [d.type, d])), [catalog])
  const initial = useMemo(() => toFlow(workflow.graph), [workflow.graph])
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>(initial.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.edges)
  const [name, setName] = useState(workflow.name)
  const [status, setStatus] = useState(workflow.status)
  const [savedSnapshot, setSavedSnapshot] = useState(() => JSON.stringify({ name: workflow.name, graph: toGraph(initial.nodes, initial.edges) }))
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [stats, setStats] = useState<Record<string, NodeStats>>({})
  const [paletteFilter, setPaletteFilter] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition, fitView } = useReactFlow()
  const theme = useTheme()

  const graph = useMemo(() => toGraph(nodes, edges), [nodes, edges])
  const dirty = JSON.stringify({ name, graph }) !== savedSnapshot
  const selected = nodes.find((n) => n.selected)
  const errorNodeIds = useMemo(() => new Set(validation?.errors.map((e) => e.node_id).filter(Boolean)), [validation])

  // Marca visualmente nós com erro de validação
  const displayNodes = useMemo(
    () => nodes.map((n) => (errorNodeIds.has(n.id) !== Boolean(n.data.hasError)
      ? { ...n, data: { ...n.data, hasError: errorNodeIds.has(n.id) } } : n)),
    [nodes, errorNodeIds],
  )

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault()
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  // Envios e CTR por bloco (atualiza a cada 30 s)
  useEffect(() => {
    const load = () => api.get<Record<string, NodeStats>>(`/api/workflows/${workflow.id}/stats`).then(setStats).catch(() => {})
    load()
    const timer = window.setInterval(load, 30_000)
    return () => window.clearInterval(timer)
  }, [workflow.id])

  const onConnect = useCallback((conn: Connection) => {
    setEdges((eds) => {
      // Cada saída tem no máximo uma conexão: a nova substitui a anterior.
      const filtered = eds.filter((e) => !(e.source === conn.source && (e.sourceHandle ?? null) === (conn.sourceHandle ?? null)))
      return addEdge({ ...conn, id: `e-${conn.source}-${conn.sourceHandle ?? 'default'}-${conn.target}`, ...defaultEdgeOptions }, filtered)
    })
  }, [setEdges])

  const isValidConnection = useCallback((conn: Connection | Edge) => {
    if (conn.source === conn.target) return false
    const target = nodes.find((n) => n.id === conn.target)
    return byType[target?.data.nodeType ?? '']?.category !== 'trigger'
  }, [nodes, byType])

  const insertNode = useCallback((def: NodeTypeDef, position: { x: number; y: number }) => {
    const node: FlowNode = {
      id: newId(def.type),
      type: 'flow',
      position,
      data: { nodeType: def.type, config: defaultConfig(def) },
      selected: true,
    }
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), node])
  }, [setNodes])

  const addNodeAtCenter = (def: NodeTypeDef) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    const center = rect
      ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 })
      : { x: 100, y: 100 }
    const offset = (nodes.length % 5) * 24
    insertNode(def, { x: center.x - NODE_WIDTH / 2 + offset, y: center.y + offset })
  }

  const onDragStart = (e: DragEvent, def: NodeTypeDef) => {
    e.dataTransfer.setData(DRAG_MIME, def.type)
    e.dataTransfer.effectAllowed = 'move'
  }

  const onDragOver = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes(DRAG_MIME)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOver(true)
  }

  const onDrop = (e: DragEvent) => {
    setDragOver(false)
    const def = byType[e.dataTransfer.getData(DRAG_MIME)]
    if (!def) return
    e.preventDefault()
    const pos = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    insertNode(def, { x: pos.x - NODE_WIDTH / 2, y: pos.y - 24 })
  }

  const updateConfig = (id: string, config: Record<string, unknown>) => {
    setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)))
    // Saídas que deixaram de existir (ex.: botão removido) perdem suas conexões
    const node = nodes.find((n) => n.id === id)
    const outputs = node ? nodeOutputs(byType[node.data.nodeType], config) : []
    setEdges((es) => es.filter((e) => e.source !== id || outputs.includes(e.sourceHandle ?? 'default')))
  }

  const deleteNode = useCallback((id: string) => {
    setNodes((ns) => ns.filter((n) => n.id !== id))
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id))
  }, [setNodes, setEdges])

  const duplicateNode = useCallback((id: string) => {
    setNodes((ns) => {
      const source = ns.find((n) => n.id === id)
      if (!source || byType[source.data.nodeType]?.category === 'trigger') return ns
      const copy: FlowNode = {
        id: newId(source.data.nodeType),
        type: 'flow',
        position: { x: source.position.x + 40, y: source.position.y + 40 },
        data: { nodeType: source.data.nodeType, config: structuredClone(source.data.config) },
        selected: true,
      }
      return [...ns.map((n) => ({ ...n, selected: false })), copy]
    })
  }, [setNodes, byType])

  const deleteEdge = useCallback((id: string) => setEdges((es) => es.filter((e) => e.id !== id)), [setEdges])

  const organize = () => {
    setNodes((ns) => autoLayout(ns, edges, byType))
    window.requestAnimationFrame(() => fitView({ padding: 0.2, maxZoom: 1, duration: 300 }))
  }

  const save = async (): Promise<boolean> => {
    setBusy(true)
    setMessage(null)
    try {
      const updated = await api.put<Workflow>(`/api/workflows/${workflow.id}`, { name: name.trim() || workflow.name, graph })
      setSavedSnapshot(JSON.stringify({ name: updated.name, graph }))
      setName(updated.name)
      setMessage({ kind: 'success', text: 'Workflow salvo.' })
      return true
    } catch (err) {
      if (err instanceof ApiError && err.code === 'WORKFLOW_INVALID') setValidation(err.details as ValidationResult)
      setMessage({ kind: 'error', text: errorMessage(err) })
      return false
    } finally {
      setBusy(false)
    }
  }

  // Atalhos: Ctrl+S salva, Ctrl+D duplica o bloco selecionado
  const shortcuts = useRef({ save, duplicate: () => {}, canSave: false })
  useEffect(() => {
    shortcuts.current = { save, duplicate: () => selected && duplicateNode(selected.id), canSave: dirty && !busy }
  })
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      const key = e.key.toLowerCase()
      if (key === 's') {
        e.preventDefault()
        if (shortcuts.current.canSave) shortcuts.current.save()
      } else if (key === 'd' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        shortcuts.current.duplicate()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const validate = async () => {
    setMessage(null)
    try {
      const result = await api.post<ValidationResult>('/api/workflows/validate', { graph })
      setValidation(result)
      if (result.valid) setMessage({ kind: 'success', text: result.warnings.length ? 'Válido, com avisos.' : 'Workflow válido!' })
    } catch (err) {
      setMessage({ kind: 'error', text: errorMessage(err) })
    }
  }

  const toggleActive = async () => {
    if (status !== 'active' && dirty && !(await save())) return
    setBusy(true)
    setMessage(null)
    try {
      const action = status === 'active' ? 'deactivate' : 'activate'
      const updated = await api.post<Workflow>(`/api/workflows/${workflow.id}/${action}`)
      setStatus(updated.status)
      setValidation(null)
      setMessage({ kind: 'success', text: updated.status === 'active' ? 'Workflow ativado!' : 'Workflow desativado.' })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'WORKFLOW_INVALID') setValidation(err.details as ValidationResult)
      setMessage({ kind: 'error', text: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const filterText = paletteFilter.trim().toLowerCase()
  const grouped = (['trigger', 'condition', 'action'] as const).map((cat) => ({
    cat,
    items: catalog.filter((d) => d.category === cat
      && (!filterText || `${d.label} ${d.description}`.toLowerCase().includes(filterText))),
  }))
  const issuesFor = (id: string) => validation?.errors.filter((e) => e.node_id === id) ?? []
  const editorActions = useMemo(() => ({ duplicateNode, deleteNode, deleteEdge, stats }),
    [duplicateNode, deleteNode, deleteEdge, stats])

  return (
    <CatalogContext.Provider value={byType}>
      <EditorContext.Provider value={editorActions}>
        <div className="editor">
          <div className="editor-toolbar">
            <Link to="/workflows" className="btn btn-ghost btn-sm">← Workflows</Link>
            <input className="input name-input" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} aria-label="Nome do workflow" />
            <WorkflowStatusBadge status={status} />
            {dirty && <span className="small muted">Alterações não salvas</span>}
            <span className="spacer" />
            {message && <span className="small" style={{ color: message.kind === 'error' ? 'var(--danger)' : 'var(--success)', maxWidth: 360 }}>{message.text}</span>}
            <button className="btn btn-sm" onClick={organize} title="Alinha os blocos automaticamente">
              <Icon name="layout" size={14} /> Organizar
            </button>
            <Link to={`/workflows/${workflow.id}/logs`} className="btn btn-sm">Logs</Link>
            <button className="btn btn-sm" onClick={validate} disabled={busy}>Validar</button>
            <button className="btn btn-sm" onClick={save} disabled={busy || !dirty} title="Ctrl+S">Salvar</button>
            <button className={`btn btn-sm ${status === 'active' ? '' : 'btn-primary'}`} onClick={toggleActive} disabled={busy}>
              {status === 'active' ? 'Desativar' : 'Salvar e ativar'}
            </button>
          </div>
          <div className="editor-body">
            <aside className="palette">
              <div className="palette-search">
                <Icon name="search" size={14} />
                <input placeholder="Buscar bloco…" value={paletteFilter} onChange={(e) => setPaletteFilter(e.target.value)} aria-label="Buscar bloco" />
              </div>
              <p className="palette-hint">Arraste para o quadro ou clique para adicionar.</p>
              {grouped.filter((g) => g.items.length).map(({ cat, items }) => (
                <div key={cat}>
                  <h3>{PALETTE_TITLES[cat]}</h3>
                  {items.map((def) => (
                    <button key={def.type} className="palette-item" draggable onDragStart={(e) => onDragStart(e, def)}
                      onClick={() => addNodeAtCenter(def)} title={def.description}
                      style={{ '--node-color': CATEGORY_META[cat].color } as CSSProperties}>
                      <span className="palette-icon"><Icon name={iconFor(def.type)} size={15} /></span>
                      <span style={{ minWidth: 0 }}>
                        <div className="pi-label">{def.label}</div>
                        <div className="pi-desc">{def.description.split('.')[0]}.</div>
                      </span>
                    </button>
                  ))}
                </div>
              ))}
            </aside>
            <div className={`canvas ${dragOver ? 'drag-over' : ''}`} ref={canvasRef}
              onDragOver={onDragOver} onDragLeave={() => setDragOver(false)} onDrop={onDrop}>
              <ReactFlow
                nodes={displayNodes}
                edges={edges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                isValidConnection={isValidConnection}
                defaultEdgeOptions={defaultEdgeOptions}
                connectionLineType={ConnectionLineType.Bezier}
                connectionLineStyle={{ stroke: 'var(--accent)', strokeWidth: 2, strokeDasharray: '6 4' }}
                connectionRadius={36}
                deleteKeyCode={['Backspace', 'Delete']}
                snapToGrid
                snapGrid={[10, 10]}
                fitView
                fitViewOptions={{ maxZoom: 1, padding: 0.2 }}
                minZoom={0.2}
                proOptions={{ hideAttribution: true }}
                colorMode={theme}
              >
                <Background variant={BackgroundVariant.Dots} gap={22} size={1.6} />
                <Controls showInteractive={false} />
                <MiniMap pannable zoomable nodeBorderRadius={8}
                  nodeColor={(n) => CATEGORY_META[byType[(n as FlowNode).data.nodeType]?.category ?? 'action']?.color ?? 'var(--text-3)'} />
              </ReactFlow>
              {nodes.length <= 1 && (
                <div className="canvas-hint">Arraste um bloco da esquerda até aqui e conecte a partir da bolinha de saída.</div>
              )}
              {validation && (validation.errors.length > 0 || validation.warnings.length > 0) && (
                <div className={`validation-panel alert ${validation.errors.length ? 'alert-error' : 'alert-warning'}`}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{validation.errors.length} erro(s), {validation.warnings.length} aviso(s)</strong>
                    <button className="btn btn-sm btn-ghost" onClick={() => setValidation(null)}>Fechar</button>
                  </div>
                  <ul>
                    {validation.errors.map((e, i) => <li key={`e${i}`}>{e.message}{e.node_id ? ` (nó ${e.node_id})` : ''}</li>)}
                    {validation.warnings.map((w, i) => <li key={`w${i}`} style={{ color: 'var(--warning)' }}>{w.message}{w.node_id ? ` (nó ${w.node_id})` : ''}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <aside className="inspector">
              {selected ? (
                <NodeInspector
                  key={selected.id}
                  def={byType[selected.data.nodeType]}
                  nodeId={selected.id}
                  config={selected.data.config}
                  issues={issuesFor(selected.id)}
                  onChange={(config) => updateConfig(selected.id, config)}
                  onDelete={() => deleteNode(selected.id)}
                />
              ) : (
                <EditorHelp />
              )}
            </aside>
          </div>
        </div>
      </EditorContext.Provider>
    </CatalogContext.Provider>
  )
}

export function WorkflowEditorPage() {
  const { id } = useParams()
  const [workflow, setWorkflow] = useState<Workflow | null>(null)
  const [catalog, setCatalog] = useState<NodeTypeDef[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.get<Workflow>(`/api/workflows/${id}`), api.get<NodeTypeDef[]>('/api/workflows/node-types')])
      .then(([wf, types]) => {
        setWorkflow(wf)
        setCatalog(types)
      })
      .catch((err) => setError(errorMessage(err)))
  }, [id])

  if (error) return <div className="page"><ErrorAlert message={error} /><Link to="/workflows">Voltar</Link></div>
  if (!workflow || !catalog) return <Loading />
  return (
    <ReactFlowProvider>
      <Editor workflow={workflow} catalog={catalog} />
    </ReactFlowProvider>
  )
}
