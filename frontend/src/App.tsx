import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import AIReviewView from './AIReviewView'
import UsernameManager from './UsernameManager'
import {
  ArrowDownToLine,
  ArrowUpRight,
  BookOpenText,
  Check,
  ChevronDown,
  CircleHelp,
  FileText,
  Filter,
  Fingerprint,
  GitBranch,
  Link2,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Trash2,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import { api } from './api'
import type { Finding, GlobalPerson, GraphEdge, GraphNode, ResearchCase, ResearchGraph, Relationship, Source } from './types'

type ModalKind = 'case' | 'person' | 'source' | 'finding' | 'relationship'
type ViewTab = 'map' | 'evidence' | 'sources' | 'ai'

const statusLabel: Record<string, string> = {
  unreviewed: 'Unreviewed',
  corroborated: 'Corroborated',
  disputed: 'Disputed',
}

function App() {
  const [cases, setCases] = useState<ResearchCase[]>([])
  const [activeCaseId, setActiveCaseId] = useState('')
  const [graph, setGraph] = useState<ResearchGraph | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [tab, setTab] = useState<ViewTab>('map')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [modal, setModal] = useState<ModalKind | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const graphBox = useRef<HTMLDivElement>(null)
  const [graphSize, setGraphSize] = useState({ width: 760, height: 600 })

  const activeCase = cases.find((item) => item.id === activeCaseId)

  const loadCases = useCallback(async () => {
    setLoading(true)
    try {
      const items = await api.cases()
      setCases(items)
      setActiveCaseId((current) => (items.some((item) => item.id === current) ? current : items[0]?.id ?? ''))
      setError('')
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not connect to the local API.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadWorkspace = useCallback(async (caseId: string) => {
    if (!caseId) {
      setGraph(null)
      setSources([])
      setFindings([])
      setRelationships([])
      setSelectedId('')
      return
    }
    try {
      const [nextGraph, nextSources, nextFindings, nextRelationships] = await Promise.all([
        api.graph(caseId),
        api.sources(caseId),
        api.findings(caseId),
        api.relationships(caseId),
      ])
      setGraph(nextGraph)
      setSources(nextSources)
      setFindings(nextFindings)
      setRelationships(nextRelationships)
      setSelectedId((current) => (nextGraph.nodes.some((node) => node.id === current) ? current : ''))
      setError('')
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not load this investigation.')
    }
  }, [])

  useEffect(() => {
    void loadCases()
  }, [loadCases])

  useEffect(() => {
    void loadWorkspace(activeCaseId)
  }, [activeCaseId, loadWorkspace])

  useEffect(() => {
    const element = graphBox.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      setGraphSize({ width: Math.max(320, Math.floor(entry.contentRect.width)), height: Math.max(400, Math.floor(entry.contentRect.height)) })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [tab, activeCaseId])

  const notify = (message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2800)
  }

  const refresh = async (caseId = activeCaseId) => {
    await Promise.all([loadCases(), loadWorkspace(caseId)])
  }

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!modal) return
    const form = new FormData(event.currentTarget)
    const value = (key: string) => String(form.get(key) ?? '').trim()
    setSaving(true)
    setError('')
    try {
      if (modal === 'case') {
        const created = await api.createCase({ title: value('title'), purpose: value('purpose') })
        await loadCases()
        setActiveCaseId(created.id)
        notify('Investigation created')
      } else if (!activeCaseId) {
        throw new Error('Create an investigation first.')
      } else if (modal === 'person') {
        const identityId = value('identity_id')
        const initialRelationship = form.get('create_relationship')
          ? {
              other_person_id: value('relationship_person_id'),
              source_id: value('relationship_source_id'),
              label: value('relationship_label'),
              details: value('relationship_details'),
              confidence: Number(value('relationship_confidence')) / 100,
              status: value('relationship_status'),
            }
          : undefined
        await api.createPerson(activeCaseId, {
          name: value('name'),
          ...(identityId ? { identity_id: identityId } : {}),
          aliases: value('aliases').split(',').map((item) => item.trim()).filter(Boolean),
          notes: value('notes'),
          ...(initialRelationship ? { initial_relationship: initialRelationship } : {}),
        })
        notify(initialRelationship ? 'Person and sourced connection saved' : identityId ? 'Existing person linked to this investigation' : 'Person added to this investigation')
      } else if (modal === 'source') {
        await api.createSource(activeCaseId, {
          url: value('url'),
          title: value('title'),
          publisher: value('publisher'),
          notes: value('notes'),
        })
        notify('Source saved')
      } else if (modal === 'finding') {
        await api.createFinding(activeCaseId, {
          person_id: value('person_id'),
          source_id: value('source_id'),
          claim: value('claim'),
          excerpt: value('excerpt'),
          confidence: Number(value('confidence')) / 100,
          status: value('status'),
        })
        notify('Source-backed finding saved')
      } else if (modal === 'relationship') {
        await api.createRelationship(activeCaseId, {
          source_person_id: value('source_person_id'),
          target_person_id: value('target_person_id'),
          source_id: value('source_id'),
          label: value('label'),
          details: value('details'),
          confidence: Number(value('confidence')) / 100,
          status: value('status'),
        })
        notify('Evidence-linked relationship saved')
      }
      setModal(null)
      await refresh()
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not save that record.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCase = async () => {
    if (!activeCase || !window.confirm(`Delete “${activeCase.title}” and all records in it? This cannot be undone.`)) return
    try {
      await api.deleteCase(activeCase.id)
      setSelectedId('')
      await loadCases()
      notify('Investigation deleted')
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not delete investigation.')
    }
  }

  const handleExport = async () => {
    if (!activeCase) return
    try {
      const payload = await api.exportCase(activeCase.id)
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${activeCase.title.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'investigation'}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      notify('Export downloaded')
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Could not export this investigation.')
    }
  }

  const nodeNames = useMemo(() => new Map((graph?.nodes ?? []).map((node) => [node.id, node.name])), [graph])
  const visibleGraph = useMemo(() => {
    if (!graph) return { nodes: [], links: [] }
    const normalized = query.trim().toLocaleLowerCase()
    if (!normalized) return { nodes: graph.nodes, links: graph.edges }
    const matches = new Set(graph.nodes.filter((node) => node.name.toLocaleLowerCase().includes(normalized) || node.aliases.some((alias) => alias.toLocaleLowerCase().includes(normalized))).map((node) => node.id))
    const ids = new Set(matches)
    graph.edges.forEach((edge) => {
      const from = typeof edge.source === 'string' ? edge.source : edge.source.id
      const to = typeof edge.target === 'string' ? edge.target : edge.target.id
      if (matches.has(from)) ids.add(to)
      if (matches.has(to)) ids.add(from)
    })
    return {
      nodes: graph.nodes.filter((node) => ids.has(node.id)),
      links: graph.edges.filter((edge) => {
        const from = typeof edge.source === 'string' ? edge.source : edge.source.id
        const to = typeof edge.target === 'string' ? edge.target : edge.target.id
        return ids.has(from) && ids.has(to)
      }),
    }
  }, [graph, query])

  const selectedPerson = graph?.nodes.find((node) => node.id === selectedId)
  const selectedFindings = findings.filter((finding) => finding.person_id === selectedId)
  const selectedLinks = relationships.filter((link) => link.source_person_id === selectedId || link.target_person_id === selectedId)

  const renderNode = (node: GraphNode & { x?: number; y?: number }, context: CanvasRenderingContext2D, scale: number) => {
    const highlighted = !query || node.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()) || node.aliases.some((alias) => alias.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    const radius = node.id === selectedId ? 6.5 : 5
    context.beginPath()
    context.arc(node.x ?? 0, node.y ?? 0, radius, 0, 2 * Math.PI, false)
    context.fillStyle = node.id === selectedId ? '#a99cff' : highlighted ? '#77d7c5' : '#46505e'
    context.shadowBlur = node.id === selectedId ? 16 : 8
    context.shadowColor = node.id === selectedId ? '#8c7cf0' : '#45ae9c'
    context.fill()
    context.shadowBlur = 0
    const label = node.name
    const fontSize = Math.max(10, 12 / scale)
    context.font = `${fontSize}px Inter, system-ui, sans-serif`
    context.textAlign = 'left'
    context.textBaseline = 'middle'
    context.fillStyle = highlighted ? '#e8edf4' : '#6e7887'
    context.fillText(label, (node.x ?? 0) + radius + 6, node.y ?? 0)
  }

  const openModal = (kind: ModalKind) => {
    if (kind !== 'case' && !activeCaseId) {
      setModal('case')
      return
    }
    setModal(kind)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Fingerprint size={18} /></div><span>fieldnotes</span><span className="brand-beta">LOCAL</span></div>
        <div className="sidebar-label-row"><span>WORKSPACE</span><button className="icon-button tiny" title="Create investigation" onClick={() => openModal('case')}><Plus size={15} /></button></div>
        <div className="case-list">
          {cases.map((item) => (
            <button key={item.id} className={`case-item ${item.id === activeCaseId ? 'active' : ''}`} onClick={() => { setActiveCaseId(item.id); setQuery(''); setTab('map') }}>
              <span className="case-dot" />
              <span className="case-name">{item.title}</span>
              {item.id === activeCaseId && <ChevronDown size={13} className="case-chevron" />}
            </button>
          ))}
          {!cases.length && !loading && <div className="sidebar-empty">No investigations yet</div>}
        </div>
        <button className="new-case-button" onClick={() => openModal('case')}><Plus size={15} /> New investigation</button>
        <div className="sidebar-section">
          <div className="sidebar-label">RESEARCH TOOLS</div>
          <button className="side-link" onClick={() => setTab('map')}><GitBranch size={15} /> Relationship map</button>
          <button className="side-link" onClick={() => setTab('evidence')}><FileText size={15} /> Findings & evidence</button>
          <button className="side-link" onClick={() => setTab('sources')}><BookOpenText size={15} /> Source library</button>
          <button className="side-link" onClick={() => setTab('ai')}><Sparkles size={15} /> AI review</button>
        </div>
        <div className="sidebar-bottom">
          <div className="privacy-card"><ShieldCheck size={16} /><div><strong>Local workspace</strong><span>Saved locally; AI shares only selected material with your consent.</span></div></div>
          <div className="sidebar-foot"><span className="online-dot" /> Local app · v0.2</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Research</span><span className="crumb-separator">/</span><strong>{activeCase?.title ?? 'Workspace'}</strong></div>
          <div className="top-actions">
            {activeCase && <button className="quiet-button" onClick={handleExport}><ArrowDownToLine size={15} /> Export</button>}
            {activeCase && <button className="icon-button" title="Delete investigation" onClick={handleDeleteCase}><Trash2 size={15} /></button>}
            <span className="top-divider" />
            <div className="privacy-indicator"><span className="online-dot" /> Local</div>
          </div>
        </header>

        <div className="safety-strip"><ShieldAlert size={14} /><span>Research workspace, not a people-search engine. Verify identity and every claim against its source.</span><button title="About responsible research" onClick={() => setError('Record public-interest research only. This local MVP does not scrape the web. Treat connections as sourced claims, not established facts; follow source terms, applicable law, and your organization’s retention policy.')}><CircleHelp size={14} /></button></div>

        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss"><X size={15} /></button></div>}

        {!activeCase ? (
          <section className="welcome-state">
            <div className="welcome-icon"><GitBranch size={28} /></div>
            <p className="eyebrow">A private research workspace</p>
            <h1>Follow the evidence.<br /><span>See the connections.</span></h1>
            <p className="welcome-copy">Build a source-backed picture from records you have reviewed. Every finding and relationship stays attached to where it came from.</p>
            <button className="primary-button" onClick={() => setModal('case')}><Plus size={16} /> Create your first investigation</button>
            <div className="welcome-notes"><span><Check size={14} /> Evidence linked</span><span><Check size={14} /> Confidence tracked</span><span><Check size={14} /> Stored locally</span></div>
          </section>
        ) : (
          <div className="workspace">
            <div className="workspace-heading">
              <div>
                <div className="eyebrow">INVESTIGATION</div>
                <h1>{activeCase.title}</h1>
                <p>{activeCase.purpose || 'Public-interest research'} <span className="heading-dot">·</span> Updated just now</p>
              </div>
              <div className="heading-actions">
                <button className="quiet-button" onClick={() => openModal('source')}><BookOpenText size={15} /> Add source</button>
                <button className="primary-button small" onClick={() => openModal('person')}><Plus size={15} /> Add person</button>
              </div>
            </div>

            <div className="stats-row">
              <div className="stat"><UsersRound size={15} /><strong>{graph?.nodes.length ?? 0}</strong><span>people</span></div>
              <div className="stat"><Link2 size={15} /><strong>{graph?.edges.length ?? 0}</strong><span>evidence links</span></div>
              <div className="stat"><FileText size={15} /><strong>{graph?.findings_count ?? 0}</strong><span>findings</span></div>
              <div className="stat"><BookOpenText size={15} /><strong>{graph?.sources_count ?? 0}</strong><span>sources</span></div>
              <div className="stats-spacer" />
              <span className="case-id">CASE {activeCase.id.slice(0, 8).toUpperCase()}</span>
            </div>

            <div className="view-toolbar">
              <div className="view-tabs" role="tablist" aria-label="Research views">
                <button className={tab === 'map' ? 'selected' : ''} onClick={() => setTab('map')}><GitBranch size={14} /> Map</button>
                <button className={tab === 'evidence' ? 'selected' : ''} onClick={() => setTab('evidence')}><FileText size={14} /> Findings <span className="tab-count">{findings.length}</span></button>
                <button className={tab === 'sources' ? 'selected' : ''} onClick={() => setTab('sources')}><BookOpenText size={14} /> Sources <span className="tab-count">{sources.length}</span></button>
                <button className={tab === 'ai' ? 'selected' : ''} onClick={() => setTab('ai')}><Sparkles size={14} /> AI review</button>
              </div>
              <div className="toolbar-actions">
                <label className="search-box"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a person or alias…" /><kbd>/</kbd></label>
                <button className="icon-button" title="Search is local to this investigation"><Filter size={15} /></button>
              </div>
            </div>

            {tab === 'map' && (
              <div className="map-layout">
                <div className="map-card">
                  <div className="map-card-head"><div><span className="live-dot" /> <span>RELATIONSHIP MAP</span></div><span className="map-hint">Drag to arrange · Scroll to zoom · Select a person for details</span></div>
                  <div className="graph-box" ref={graphBox}>
                    <div className="graph-grid" />
                    {visibleGraph.nodes.length ? (
                      <ForceGraph2D
                        width={graphSize.width}
                        height={graphSize.height}
                        graphData={{ nodes: visibleGraph.nodes, links: visibleGraph.links }}
                        nodeId="id"
                        linkSource="source"
                        linkTarget="target"
                        backgroundColor="rgba(0,0,0,0)"
                        nodeRelSize={5}
                        nodeCanvasObjectMode={() => 'after'}
                        nodeCanvasObject={renderNode}
                        nodeColor={(node: GraphNode) => node.id === selectedId ? '#a99cff' : '#77d7c5'}
                        linkColor={(edge: GraphEdge) => edge.status === 'disputed' ? 'rgba(230,110,110,.62)' : 'rgba(119,215,197,.40)'}
                        linkWidth={(edge: GraphEdge) => edge.status === 'corroborated' ? 1.8 : 1.1}
                        linkDirectionalArrowLength={3}
                        linkDirectionalArrowRelPos={1}
                        cooldownTicks={100}
                        onNodeClick={(node: GraphNode) => setSelectedId(node.id)}
                        onBackgroundClick={() => setSelectedId('')}
                      />
                    ) : (
                      <div className="empty-map">
                        <div className="empty-map-icon"><GitBranch size={23} /></div>
                        <h2>{query ? 'No matching people' : 'Your map starts with a sourced record'}</h2>
                        <p>{query ? 'Try another name or alias.' : 'Add people, attach a public source, then record a finding or evidence-backed connection. No data is pulled automatically.'}</p>
                        {!query && <button className="primary-button small" onClick={() => openModal('person')}><Plus size={15} /> Add the first person</button>}
                      </div>
                    )}
                    <div className="map-legend"><span><i className="legend-node" /> Person</span><span><i className="legend-link" /> Sourced claim</span><span><i className="legend-dot uncertain" /> Unreviewed</span></div>
                  </div>
                  <div className="map-card-foot"><span><ShieldCheck size={14} /> Connections shown are sourced claims; confidence is not proof.</span><button onClick={() => openModal('relationship')} disabled={peopleCount(graph) < 2 || !sources.length}><Link2 size={14} /> Add connection</button></div>
                </div>
                <aside className="detail-panel">
                  {selectedPerson ? (
                    <PersonDetails caseId={activeCase.id} person={selectedPerson} findings={selectedFindings} links={selectedLinks} nodeNames={nodeNames} onAddFinding={() => openModal('finding')} />
                  ) : (
                    <div className="detail-empty"><div className="detail-icon"><Fingerprint size={20} /></div><span className="eyebrow">PERSON DETAILS</span><h3>Select a person</h3><p>Choose a node on the map to review its notes, source-backed findings, and documented connections.</p><div className="detail-tip"><ShieldCheck size={14} /><span>Ambiguous matches should stay separate until you can verify them.</span></div></div>
                  )}
                </aside>
              </div>
            )}

            {tab === 'evidence' && <EvidenceView findings={findings} onAdd={() => openModal('finding')} />}
            {tab === 'sources' && <SourcesView sources={sources} onAdd={() => openModal('source')} />}
            {tab === 'ai' && <AIReviewView key={activeCase.id} caseId={activeCase.id} sources={sources} />}

            <footer className="workspace-footer"><span>Only store what the investigation needs. Keep sources, excerpts, and retention practices appropriate to your purpose.</span><span>FIELDNOTES <i>·</i> LOCAL FIRST</span></footer>
          </div>
        )}

        {loading && <div className="loading-indicator"><LoaderCircle size={15} className="spin" /> Connecting to local workspace…</div>}
        {toast && <div className="toast"><Check size={15} /> {toast}</div>}
      </main>

      {modal && <Modal kind={modal} people={graph?.nodes ?? []} sources={sources} saving={saving} onClose={() => setModal(null)} onSubmit={handleCreate} />}
    </div>
  )
}

function peopleCount(graph: ResearchGraph | null) {
  return graph?.nodes.length ?? 0
}

function PersonDetails({
  caseId,
  person,
  findings,
  links,
  nodeNames,
  onAddFinding,
}: {
  caseId: string
  person: GraphNode
  findings: Finding[]
  links: Relationship[]
  nodeNames: Map<string, string>
  onAddFinding: () => void
}) {
  return (
    <div className="person-details">
      <div className="detail-panel-top"><span className="eyebrow">PERSON RECORD</span><span className="record-marker"><UserRound size={14} /></span></div>
      <div className="person-avatar">{person.name.split(/\s+/).slice(0, 2).map((name) => name[0]).join('').toUpperCase()}</div>
      <h2>{person.name}</h2>
      {person.aliases.length > 0 && <div className="aliases">Also recorded as {person.aliases.join(' · ')}</div>}
      <div className="identity-caution"><ShieldAlert size={14} /><span>Identity match not independently verified</span></div>
      {person.notes && <p className="person-notes">{person.notes}</p>}
      <div className="detail-divider" />
      <UsernameManager caseId={caseId} personId={person.id} />
      <div className="detail-divider" />
      <div className="detail-section-head"><span>Source-backed findings</span><button onClick={onAddFinding} title="Add finding"><Plus size={14} /></button></div>
      {!findings.length ? <p className="detail-muted">No findings recorded for this person.</p> : findings.map((finding) => (
        <article className="finding-card" key={finding.id}>
          <div className="finding-status"><span className={`status-dot ${finding.status}`} />{statusLabel[finding.status]}<span className="confidence">{Math.round(finding.confidence * 100)}% confidence</span></div>
          <p>{finding.claim}</p>
          {finding.excerpt && <blockquote>{finding.excerpt}</blockquote>}
          <a href={finding.source.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">{finding.source.title}<ArrowUpRight size={12} /></a>
          <time>Retrieved {finding.source.retrieved_on}</time>
        </article>
      ))}
      <div className="detail-divider" />
      <div className="detail-section-head"><span>Documented connections</span><span className="count-pill">{links.length}</span></div>
      {!links.length ? <p className="detail-muted">No sourced connections yet.</p> : links.map((link) => {
        const other = link.source_person_id === person.id ? link.target_person_id : link.source_person_id
        return <article className="connection-row" key={link.id}><div className="connection-icon"><Link2 size={13} /></div><div><strong>{nodeNames.get(other) ?? 'Unknown person'}</strong><span>{link.label}</span><a href={link.source.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">{link.source.title} · {Math.round(link.confidence * 100)}%</a></div></article>
      })}
      <div className="detail-footnote"><ShieldCheck size={13} /> Relationship language reflects the cited source, not an app-generated conclusion.</div>
    </div>
  )
}

function EvidenceView({ findings, onAdd }: { findings: Finding[]; onAdd: () => void }) {
  return (
    <section className="records-view">
      <div className="records-head"><div><div className="eyebrow">RESEARCH LOG</div><h2>Findings & evidence</h2><p>Each claim is linked to its source and review state.</p></div><button className="primary-button small" onClick={onAdd} disabled={!findings.length && false}><Plus size={15} /> Add finding</button></div>
      {!findings.length ? <div className="records-empty"><FileText size={22} /><h3>No findings yet</h3><p>Add a person and a source, then record a concise claim that the source supports.</p></div> : <div className="evidence-list">{findings.map((finding) => (
        <article className="evidence-item" key={finding.id}>
          <div className="evidence-icon"><FileText size={16} /></div>
          <div className="evidence-content"><div className="evidence-topline"><span className="person-tag"><UserRound size={12} /> {finding.person_name}</span><span className={`review-pill ${finding.status}`}><span className={`status-dot ${finding.status}`} />{statusLabel[finding.status]}</span></div><h3>{finding.claim}</h3>{finding.excerpt && <blockquote>{finding.excerpt}</blockquote>}<a href={finding.source.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer">{finding.source.title}<ArrowUpRight size={13} /></a><div className="evidence-meta"><span>Retrieved {finding.source.retrieved_on}</span><span>{Math.round(finding.confidence * 100)}% confidence</span></div></div>
        </article>
      ))}</div>}
    </section>
  )
}

function SourcesView({ sources, onAdd }: { sources: Source[]; onAdd: () => void }) {
  return (
    <section className="records-view">
      <div className="records-head"><div><div className="eyebrow">SOURCE LIBRARY</div><h2>Public sources</h2><p>Store references you have reviewed. The app does not fetch or archive source pages.</p></div><button className="primary-button small" onClick={onAdd}><Plus size={15} /> Add source</button></div>
      {!sources.length ? <div className="records-empty"><BookOpenText size={22} /><h3>No sources yet</h3><p>Add the source URL, title, publisher, and any notes needed to revisit it.</p></div> : <div className="source-grid">{sources.map((source) => <article className="source-card" key={source.id}><div className="source-card-icon"><BookOpenText size={17} /></div><div className="source-title-line"><span className="eyebrow">{source.publisher || 'PUBLIC SOURCE'}</span><a href={source.url} target="_blank" rel="noreferrer" referrerPolicy="no-referrer" title="Open source in a new tab"><ArrowUpRight size={14} /></a></div><h3>{source.title}</h3><p className="source-domain">{source.url}</p>{source.notes && <p className="source-notes">{source.notes}</p>}<div className="source-date">Retrieved <time>{source.retrieved_on}</time>{source.published_on && <span> · Published {source.published_on}</span>}</div></article>)}</div>}
    </section>
  )
}

function Modal({
  kind,
  people,
  sources,
  saving,
  onClose,
  onSubmit,
}: {
  kind: ModalKind
  people: GraphNode[]
  sources: Source[]
  saving: boolean
  onClose: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  const [personMode, setPersonMode] = useState<'new' | 'link'>('new')
  const [globalQuery, setGlobalQuery] = useState('')
  const [globalPeople, setGlobalPeople] = useState<GlobalPerson[]>([])
  const [selectedIdentity, setSelectedIdentity] = useState<GlobalPerson | null>(null)
  const [globalLoading, setGlobalLoading] = useState(false)
  const [globalError, setGlobalError] = useState('')
  const [addInitialRelationship, setAddInitialRelationship] = useState(false)

  useEffect(() => {
    if (kind !== 'person' || personMode !== 'link') return
    let active = true
    setGlobalLoading(true)
    setGlobalError('')
    api.globalPeople(globalQuery).then((results) => {
      if (active) setGlobalPeople(results)
    }).catch((problem) => {
      if (active) {
        setGlobalPeople([])
        setGlobalError(problem instanceof Error ? problem.message : 'Could not search the shared people directory.')
      }
    }).finally(() => {
      if (active) setGlobalLoading(false)
    })
    return () => { active = false }
  }, [kind, personMode, globalQuery])

  const titles: Record<ModalKind, string> = {
    case: 'New investigation',
    person: 'Add a person',
    source: 'Add a public source',
    finding: 'Record a finding',
    relationship: 'Document a connection',
  }
  const descriptions: Record<ModalKind, string> = {
    case: 'Keep each research effort in its own workspace.',
    person: 'Create a shared person identity or link one already used in another workspace. Case notes remain separate.',
    source: 'Save a reference you reviewed. This app will not retrieve the page.',
    finding: 'Write only what the selected source supports; preserve wording when useful.',
    relationship: 'Describe the sourced association. This is a claim for review, not an established fact.',
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-head"><div><div className="eyebrow">LOCAL RESEARCH</div><h2 id="modal-title">{titles[kind]}</h2><p>{descriptions[kind]}</p></div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={17} /></button></div>
        <form onSubmit={onSubmit}>
          {kind === 'case' && <><Field label="Investigation title" name="title" placeholder="e.g. Public procurement review" required maxLength={180} autoFocus /><Field label="Purpose / context" name="purpose" placeholder="Why is this research being conducted?" maxLength={500} /></>}
          {kind === 'person' && <>
            <div className="person-mode-switch" role="group" aria-label="Person entry mode">
              <button type="button" className={personMode === 'new' ? 'selected' : ''} onClick={() => setPersonMode('new')}>Create new identity</button>
              <button type="button" className={personMode === 'link' ? 'selected' : ''} onClick={() => setPersonMode('link')}>Link shared person</button>
            </div>
            {personMode === 'new' ? (
              <Field label="Display name" name="name" placeholder="Name as shown in your source" required maxLength={140} autoFocus />
            ) : (
              <div className="shared-person-picker">
                <label className="form-field"><span>Search the shared people directory</span><input value={globalQuery} onChange={(event) => setGlobalQuery(event.target.value)} placeholder="Type a name…" maxLength={140} autoFocus /></label>
                <label className="form-field"><span>Person identity *</span><select value={selectedIdentity?.id ?? ''} onChange={(event) => setSelectedIdentity(globalPeople.find((person) => person.id === event.target.value) ?? null)} required><option value="" disabled>{globalLoading ? 'Searching…' : globalPeople.length ? 'Choose a shared person…' : 'No matching shared people'}</option>{globalPeople.map((person) => <option key={person.id} value={person.id}>{person.canonical_name}</option>)}</select></label>
                {globalError && <p className="form-error">{globalError}</p>}
                {selectedIdentity && <><input type="hidden" name="identity_id" value={selectedIdentity.id} /><input type="hidden" name="name" value={selectedIdentity.canonical_name} /><div className="shared-person-note"><UserRound size={15} /><span>Linking <strong>{selectedIdentity.canonical_name}</strong>. Aliases and notes below are saved only in this investigation.</span></div></>}
              </div>
            )}
            <Field label="Aliases for this investigation (comma-separated)" name="aliases" placeholder="Only include publicly documented names" />
            <TextArea label="Notes for this investigation" name="notes" placeholder="Context, identity caveats, or next verification step…" maxLength={5000} />
            <div className="initial-relationship-toggle"><label><input type="checkbox" name="create_relationship" value="yes" checked={addInitialRelationship} disabled={!people.length || !sources.length} onChange={(event) => setAddInitialRelationship(event.target.checked)} /><span><strong>Create a connection now</strong><small>Optional; it must cite a source already in this workspace.</small></span></label></div>
            {addInitialRelationship && <div className="initial-relationship-fields"><SelectField label="Connect to person" name="relationship_person_id" options={people.map((person) => [person.id, person.name])} required /><SelectField label="Supporting source" name="relationship_source_id" options={sources.map((source) => [source.id, source.title])} required /><Field label="Connection label" name="relationship_label" placeholder="e.g. Listed as co-directors in filing" required maxLength={240} /><TextArea label="What the source shows" name="relationship_details" placeholder="Keep the claim narrow and evidence-backed" maxLength={5000} /><RangeField label="Researcher confidence" name="relationship_confidence" initial="50" /><SelectField label="Review status" name="relationship_status" options={Object.entries(statusLabel).map(([key, label]) => [key, label])} required /></div>}
          </>}
          {kind === 'source' && <><Field label="Source URL" name="url" type="url" placeholder="https://…" required maxLength={2048} autoFocus /><Field label="Source title" name="title" placeholder="Article, document, or public record title" required maxLength={250} /><Field label="Publisher" name="publisher" placeholder="Organization or publication" maxLength={180} /><TextArea label="Reference notes" name="notes" placeholder="Page number, access notes, or context (no page is fetched)" maxLength={5000} /></>}
          {kind === 'finding' && <><SelectField label="Person" name="person_id" options={people.map((person) => [person.id, person.name])} required /><SelectField label="Supporting source" name="source_id" options={sources.map((source) => [source.id, source.title])} required /><TextArea label="Finding / claim" name="claim" placeholder="State the narrow claim supported by the source" required maxLength={2000} /><TextArea label="Supporting excerpt (optional)" name="excerpt" placeholder="Short excerpt or page reference; avoid unnecessary sensitive detail" maxLength={5000} /><RangeField label="Researcher confidence" name="confidence" initial="65" /><SelectField label="Review status" name="status" options={Object.entries(statusLabel).map(([key, label]) => [key, label])} required /></>}
          {kind === 'relationship' && <><SelectField label="Person A" name="source_person_id" options={people.map((person) => [person.id, person.name])} required /><SelectField label="Person B" name="target_person_id" options={people.map((person) => [person.id, person.name])} required /><Field label="Connection label" name="label" placeholder="e.g. Listed as co-directors in filing" required maxLength={240} /><SelectField label="Supporting source" name="source_id" options={sources.map((source) => [source.id, source.title])} required /><TextArea label="What the source shows" name="details" placeholder="Describe only the evidence-backed association; avoid implying more than the source establishes" maxLength={5000} /><RangeField label="Researcher confidence" name="confidence" initial="55" /><SelectField label="Review status" name="status" options={Object.entries(statusLabel).map(([key, label]) => [key, label])} required /></>}
          <div className="modal-safety"><ShieldAlert size={14} /><span>Do not enter passwords, private contact details, sensitive personal traits, or information you do not need.</span></div>
          <div className="modal-actions"><button type="button" className="quiet-button" onClick={onClose} disabled={saving}>Cancel</button><button type="submit" className="primary-button" disabled={saving || ((kind === 'finding' || kind === 'relationship') && (!people.length || !sources.length)) || (kind === 'person' && addInitialRelationship && (!people.length || !sources.length))}>{saving && <LoaderCircle size={15} className="spin" />}{saving ? 'Saving…' : titles[kind]}</button></div>
        </form>
      </section>
    </div>
  )
}

function Field({ label, name, placeholder, required, maxLength, type = 'text', autoFocus = false }: { label: string; name: string; placeholder: string; required?: boolean; maxLength?: number; type?: string; autoFocus?: boolean }) {
  return <label className="form-field"><span>{label}{required && <i> *</i>}</span><input name={name} type={type} placeholder={placeholder} required={required} maxLength={maxLength} autoFocus={autoFocus} /></label>
}

function TextArea({ label, name, placeholder, required, maxLength }: { label: string; name: string; placeholder: string; required?: boolean; maxLength?: number }) {
  return <label className="form-field"><span>{label}{required && <i> *</i>}</span><textarea name={name} placeholder={placeholder} required={required} maxLength={maxLength} rows={3} /></label>
}

function SelectField({ label, name, options, required }: { label: string; name: string; options: [string, string][]; required?: boolean }) {
  return <label className="form-field"><span>{label}{required && <i> *</i>}</span><select name={name} required={required} defaultValue=""><option value="" disabled>{options.length ? 'Choose a record…' : 'Add a person and source first'}</option>{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></label>
}

function RangeField({ label, name, initial }: { label: string; name: string; initial: string }) {
  const [value, setValue] = useState(Number(initial))
  return <label className="form-field range-field"><span>{label}<strong>{value}%</strong></span><input name={name} type="range" min="0" max="100" step="5" value={value} onChange={(event) => setValue(Number(event.target.value))} /></label>
}

export default App
