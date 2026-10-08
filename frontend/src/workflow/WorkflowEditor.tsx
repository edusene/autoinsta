import {
  addEdge,
  Background,
  Controls,
  MarkerType,
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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorAlert, Loading, WorkflowStatusBadge } from '../components/ui'
import { api, ApiError, errorMessage } from '../lib/api'
import { useTheme } from '../lib/theme'
import type { Graph, NodeTypeDef, ValidationResult, Workflow } from '../types'
import { CATEGORY_META, CatalogContext, defaultConfig, type FlowNode } from './catalog'
import { FlowNodeView } from './FlowNodeView'
import { EditorHelp, NodeInspector } from './NodeInspector'

const nodeTypes = { flow: FlowNodeView }
const PALETTE_TITLES = { trigger: 'Gatilhos', condition: 'Condições', action: 'Ações' }
const defaultEdgeOptions = { type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }

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
  const canvasRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()
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

  const addNode = (def: NodeTypeDef) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    const center = rect
      ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 3 })
      : { x: 100, y: 100 }
    const offset = (nodes.length % 5) * 24
    const node: FlowNode = {
      id: newId(def.type),
      type: 'flow',
      position: { x: center.x - 120 + offset, y: center.y + offset },
      data: { nodeType: def.type, config: defaultConfig(def) },
      selected: true,
    }
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), node])
  }

  const updateConfig = (id: string, config: Record<string, unknown>) => {
    setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)))
  }

  const deleteNode = (id: string) => {
    setNodes((ns) => ns.filter((n) => n.id !== id))
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id))
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

  const grouped = (['trigger', 'condition', 'action'] as const).map((cat) => ({ cat, items: catalog.filter((d) => d.category === cat) }))
  const issuesFor = (id: string) => validation?.errors.filter((e) => e.node_id === id) ?? []

  return (
    <CatalogContext.Provider value={byType}>
      <div className="editor">
        <div className="editor-toolbar">
          <Link to="/workflows" className="btn btn-ghost btn-sm">← Workflows</Link>
          <input className="input name-input" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} aria-label="Nome do workflow" />
          <WorkflowStatusBadge status={status} />
          {dirty && <span className="small muted">Alterações não salvas</span>}
          <span className="spacer" />
          {message && <span className="small" style={{ color: message.kind === 'error' ? 'var(--danger)' : 'var(--success)', maxWidth: 360 }}>{message.text}</span>}
          <Link to={`/workflows/${workflow.id}/logs`} className="btn btn-sm">Logs</Link>
          <button className="btn btn-sm" onClick={validate} disabled={busy}>Validar</button>
          <button className="btn btn-sm" onClick={save} disabled={busy || !dirty}>Salvar</button>
          <button className={`btn btn-sm ${status === 'active' ? '' : 'btn-primary'}`} onClick={toggleActive} disabled={busy}>
            {status === 'active' ? 'Desativar' : 'Salvar e ativar'}
          </button>
        </div>
        <div className="editor-body">
          <aside className="palette">
            {grouped.map(({ cat, items }) => (
              <div key={cat}>
                <h3>{PALETTE_TITLES[cat]}</h3>
                {items.map((def) => (
                  <button key={def.type} className="palette-item" onClick={() => addNode(def)} title={def.description}>
                    <span className="palette-dot" style={{ background: CATEGORY_META[cat].color }} />
                    <span>
                      <div className="pi-label">{def.label}</div>
                      <div className="pi-desc">{def.description.split('.')[0]}.</div>
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </aside>
          <div className="canvas" ref={canvasRef}>
            <ReactFlow
              nodes={displayNodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              isValidConnection={isValidConnection}
              defaultEdgeOptions={defaultEdgeOptions}
              deleteKeyCode={['Backspace', 'Delete']}
              fitView
              fitViewOptions={{ maxZoom: 1 }}
              proOptions={{ hideAttribution: true }}
              colorMode={theme}
            >
              <Background gap={20} />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
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
