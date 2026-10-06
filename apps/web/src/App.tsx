import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, ArrowRight, Check, ChevronDown, ChevronRight, Circle, Clock3, Crosshair, Download, Eye, EyeOff, Focus, Grid2X2, Info, Layers2, MessageCircle, MoreHorizontal, Move3D, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Plus, RotateCcw, Send, ShieldCheck, Sparkles, Square } from 'lucide-react'
import type { Build, Feature, Project, Proposal, Spec, TemplateId } from './types'

const ModelCanvas = lazy(() => import('./Scene').then((mod) => ({ default: mod.ModelCanvas })))

const API = 'http://127.0.0.1:8000/api'
const API_ROOT = 'http://127.0.0.1:8000'
const LABELS: Record<TemplateId, string> = { rectangular_plate: 'Mounting plate', circular_plate: 'Round plate', l_bracket: 'L bracket', u_channel: 'U channel', z_bracket: 'Z bracket' }
const ICONS: Record<TemplateId, string> = { rectangular_plate: 'plate', circular_plate: 'round', l_bracket: 'l', u_channel: 'u', z_bracket: 'z' }
const MM_PER_IN = 25.4
const modelUrl = (p: Project | null) => p?.build?.glb_url ? `${API_ROOT}${p.build.glb_url}` : undefined

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  const value = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(value.detail ?? `Request failed (${response.status})`)
  return value as T
}

function ShapeIcon({ kind, size = 'normal' }: { kind: string; size?: 'normal' | 'large' }) {
  return <span className={`shape-icon ${size}`} aria-hidden="true"><span className={`shape shape-${kind}`} /></span>
}

function prettyFeature(feature: Feature, factor: number, units: string) {
  return Object.entries(feature.dimensions).filter(([key]) => !['x','y'].includes(key)).map(([key, val]) => `${key.replaceAll('_', ' ')} ${typeof val === 'number' ? `${(val / factor).toFixed(val / factor % 1 === 0 ? 0 : 1)} ${units}` : val}`).join(' · ')
}

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [recent, setRecent] = useState<Project[]>([])
  const [aiReady, setAiReady] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState('')
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [prompt, setPrompt] = useState('')
  const [selectedFeature, setSelectedFeature] = useState<string>('overall')
  const [mode, setMode] = useState<'shaded' | 'edges' | 'translucent'>('shaded')
  const [cameraPreset, setCameraPreset] = useState('iso')
  const [cameraReset, setCameraReset] = useState(0)
  const [cameraKind, setCameraKind] = useState<'perspective' | 'orthographic'>('perspective')
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [rightTab, setRightTab] = useState<'dimensions' | 'features' | 'checks'>('dimensions')
  const [mobileTab, setMobileTab] = useState<'model' | 'chat' | 'details'>('model')
  const [showDimensions, setShowDimensions] = useState(true)
  const [revisions, setRevisions] = useState<Project[]>([])
  const [healthError, setHealthError] = useState(false)
  const [description, setDescription] = useState('')
  const saveTimer = useRef<number | null>(null)
  const workspaceRef = useRef<HTMLElement>(null)

  const refreshProjects = useCallback(async () => {
    try { setRecent(await request<Project[]>('/projects')) } catch { /* backend may still be starting */ }
  }, [])

  useEffect(() => {
    void request<{ ai_configured: boolean }>('/health').then((v) => { setAiReady(v.ai_configured); setHealthError(false) }).catch(() => { setHealthError(true); setAiReady(false) })
    void refreshProjects()
    const handle = window.setInterval(() => { void request<{ ai_configured: boolean }>('/health').then((v) => { setAiReady(v.ai_configured); setHealthError(false) }).catch(() => setHealthError(true)) }, 10000)
    return () => window.clearInterval(handle)
  }, [refreshProjects])

  const pollBuild = useCallback(async (projectId: string, jobId: string) => {
    setBuilding(true)
    for (let i = 0; i < 240; i += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 750))
      try {
        const job = await request<{ status: string; result?: Build | null }>(`/jobs/${jobId}`)
        const current = await request<Project>(`/projects/${projectId}`)
        setProject(current)
        if (job.status === 'succeeded' || job.status === 'failed') {
          setBuilding(false)
          if (job.result?.geometry_status === 'invalid') setError(job.result.findings[0]?.detail ?? 'Could not generate the model.')
          void refreshProjects()
          return
        }
      } catch (e) { setBuilding(false); setError(e instanceof Error ? e.message : 'Build status unavailable.'); return }
    }
    setBuilding(false)
    setError('The model is taking longer than expected. Your project is saved; check back shortly.')
  }, [refreshProjects])

  const createFromTemplate = async (template: TemplateId, promptText = '') => {
    setError(''); setProposal(null); setBusy(true)
    try {
      const created = await request<Project>('/projects', { method: 'POST', body: JSON.stringify({ name: LABELS[template], template_id: template }) })
      setProject(created)
      const job = await request<{ id: string }>(`/projects/${created.id}/build`, { method: 'POST' })
      if (promptText.trim()) {
        setPrompt(promptText)
        void sendMessage(created, promptText, job.id)
      } else void pollBuild(created.id, job.id)
      setDescription('')
      await refreshProjects()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create the project.') }
    finally { setBusy(false) }
  }

  const openProject = async (id: string) => {
    setBusy(true); setError(''); setProposal(null)
    try {
      const next = await request<Project>(`/projects/${id}`)
      setProject(next)
      setMobileTab('model')
      const history = await request<Project[]>(`/projects/${id}/revisions`)
      setRevisions(history)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not open project.') }
    finally { setBusy(false) }
  }

  const sendMessage = async (current = project, text = prompt, firstJob?: string) => {
    if (!current || !text.trim()) return
    const message = text.trim()
    setPrompt(''); setError(''); setProposal(null); setBusy(true)
    try {
      const result = await request<{ project: Project; proposal: Proposal }>(`/projects/${current.id}/chat`, { method: 'POST', body: JSON.stringify({ message, based_on_revision: current.revision }) })
      setProject(result.project); setProposal(result.proposal)
      const fullHistory = await request<Project[]>(`/projects/${current.id}/revisions`)
      setRevisions(fullHistory)
      if (firstJob) void pollBuild(current.id, firstJob)
    } catch (e) { setPrompt(message); setError(e instanceof Error ? e.message : 'Could not get an AI proposal.'); if (firstJob) void pollBuild(current.id, firstJob) }
    finally { setBusy(false) }
  }

  const applySpec = async (spec: Spec) => {
    if (!project) return
    setError(''); setBusy(true); setProposal(null)
    try {
      const result = await request<{ project: Project; job: { id: string } }>(`/projects/${project.id}/spec`, { method: 'PUT', body: JSON.stringify({ based_on_revision: project.revision, spec }) })
      setProject(result.project)
      void pollBuild(project.id, result.job.id)
      setRevisions(await request<Project[]>(`/projects/${project.id}/revisions`))
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not apply this edit.') }
    finally { setBusy(false) }
  }

  const updateField = (key: string, shown: number) => {
    if (!project) return
    const factor = project.display_units === 'in' ? MM_PER_IN : 1
    const spec = structuredClone(project.spec)
    spec.parameters[key] = shown * factor
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => { void applySpec(spec) }, 450)
  }

  const addHole = () => {
    if (!project) return
    const spec = structuredClone(project.spec)
    const p = spec.parameters
    const round = project.spec.template_id === 'circular_plate'
    const x = round ? 0 : (p.length ?? p.base_length ?? p.base_width ?? 100) / 2
    const y = round ? 0 : (p.width ?? p.length ?? 70) / 2
    spec.holes.push({ x, y, diameter: 6.5 })
    void applySpec(spec)
  }

  const setUnits = async (units: 'mm' | 'in') => {
    if (!project || units === project.display_units) return
    try { setProject(await request<Project>(`/projects/${project.id}`, { method: 'PUT', body: JSON.stringify({ display_units: units }) })) } catch (e) { setError(e instanceof Error ? e.message : 'Could not change units.') }
  }

  const loadRevision = async (revision: number) => {
    if (!project) return
    setBusy(true)
    try {
      const result = await request<Project>(`/projects/${project.id}/restore/${revision}`, { method: 'POST' })
      setProject(result)
      const job = await request<{ id: string }>(`/projects/${project.id}/build`, { method: 'POST' })
      void pollBuild(project.id, job.id)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not restore the revision.') }
    finally { setBusy(false) }
  }

  const download = () => { if (project?.build?.export_url && project.build.revision === project.revision && project.build.geometry_status === 'valid') window.location.assign(`${API_ROOT}${project.build.export_url}`) }
  const factor = project?.display_units === 'in' ? MM_PER_IN : 1
  const units = project?.display_units ?? 'mm'
  const build = project?.build
  const features = build?.features ?? []
  const selected = features.find((f) => f.id === selectedFeature) ?? features[0]
  const conversations = project?.conversation.filter((m) => ['user','assistant'].includes(m.role)) ?? []

  if (!project) return <main className="landing">
    <header className="landing-nav"><a className="brand" href="#top"><span className="brand-mark">F</span><span>foldspec<span className="brand-dot">.</span></span></a><div className="nav-right"><span className="local-pill"><i /> Local workspace</span><button className="icon-button subtle" title="More options"><MoreHorizontal size={19} /></button></div></header>
    <section className="hero" id="top">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot" />A NEW WAY TO MAKE THINGS</div>
        <h1>Your idea,<br /><span>made tangible.</span></h1>
        <p className="hero-sub">Describe what you need. Fine-tune every detail. Leave with a model that’s ready to make.</p>
        <form className="prompt-card" onSubmit={(e) => { e.preventDefault(); void createFromTemplate('rectangular_plate', description.trim()) }}>
          <Sparkles size={18} className="prompt-spark" /><textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What are we making? Describe an idea, a size, or what it needs to fit…" rows={3} aria-label="Describe your sheet-metal part" />
          <div className="prompt-footer"><span>START WITH A DESCRIPTION</span><button className="button primary" type="submit" disabled={busy}>{busy ? 'Opening…' : <>Start designing <ArrowRight size={16} /></>}</button></div>
        </form>
        {error && <div className="alert error"><AlertTriangle size={16} />{error}</div>}
      </div>
      <div className="hero-art" aria-hidden="true"><div className="art-glow" /><div className="art-grid" /><div className="art-dim dim-a"><span>80 mm</span><i /></div><div className="art-dim dim-b"><span>42 mm</span><i /></div><div className="art-tag"><span className="tiny-green" />PARAMETRIC STUDY <b>01</b></div><div className="art-bracket"><div className="art-top" /><div className="art-wall" /><div className="art-hole hole-a" /><div className="art-hole hole-b" /><div className="art-hole hole-c" /><div className="art-hole hole-d" /></div><div className="art-base-shadow" /><div className="art-coordinate">X <i />Y <i />Z</div></div>
    </section>
    <section className="templates-section"><div className="section-head"><div><div className="eyebrow muted">A PLACE TO BEGIN</div><h2>Start with a shape.</h2></div><span className="section-note">FIVE FOUNDATIONS <span>·</span> MADE YOURS</span></div>
      <div className="template-grid">{(Object.keys(LABELS) as TemplateId[]).map((id, idx) => <button className="template-card" key={id} onClick={() => void createFromTemplate(id)} disabled={busy}><div className="template-preview"><span className="recipe-index">0{idx+1}</span><ShapeIcon kind={ICONS[id]} size="large" /><span className="template-arrow"><ArrowRight size={17} /></span></div><div className="template-meta"><span>{LABELS[id]}</span><span>Start with template</span></div></button>)}</div>
    </section>
    <section className="recent-section"><div className="section-head"><div><div className="eyebrow muted">PICK UP WHERE YOU LEFT OFF</div><h2>Your recent work.</h2></div><span className="section-note">SAVED ON THIS DEVICE</span></div>
      {recent.length ? <div className="recent-grid">{recent.slice(0,3).map((p) => <button key={p.id} className="recent-card" onClick={() => void openProject(p.id)}><ShapeIcon kind={ICONS[p.spec.template_id]} /><span className="recent-copy"><b>{p.name}</b><small>Revision {p.revision} <i>·</i> {p.spec.template_id.replaceAll('_',' ')}</small></span><ChevronRight size={17} /></button>)}</div> : <p className="empty-recent">Your designs will show up here. They stay on this device.</p>}</section>
    <footer className="landing-footer"><span>foldspec<span className="brand-dot">.</span></span><span>DESIGNED TO TAKE AN IDEA FURTHER</span><span>PROTOTYPE · LOCAL ONLY</span></footer>
  </main>

  const revisionOptions = revisions.some((r) => r.revision === project.revision) ? revisions : [project, ...revisions]
  return <main className={`workspace ${mobileTab}`} ref={workspaceRef}>
    <header className="workbar"><a className="brand compact" href="#home" onClick={(e) => { e.preventDefault(); setProject(null); setError('') }}><span className="brand-mark">F</span><span>foldspec<span className="brand-dot">.</span></span></a><span className="bar-divider" /><div className="project-heading"><input aria-label="Project name" value={project.name} onChange={(e) => setProject({ ...project, name: e.target.value })} onBlur={() => void request(`/projects/${project.id}`, { method: 'PUT', body: JSON.stringify({ name: project.name }) })} /><span><span className="save-dot" />{building ? `Building revision ${project.revision}` : 'Saved on this device'}</span></div><div className="workbar-right"><label className="revision-select"><Clock3 size={14} /><select aria-label="Design revision" value={project.revision} onChange={(e) => void loadRevision(Number(e.target.value))}>{revisionOptions.map((r) => <option value={r.revision} key={r.revision}>Rev {r.revision}{r.revision === project.revision ? ' · Current' : ''}</option>)}</select><ChevronDown size={13} /></label><div className="unit-switch"><button className={units === 'mm' ? 'active' : ''} onClick={() => void setUnits('mm')}>mm</button><button className={units === 'in' ? 'active' : ''} onClick={() => void setUnits('in')}>in</button></div><button className="button primary export-top" onClick={download} disabled={!build || build.geometry_status !== 'valid' || build.revision !== project.revision}><Download size={15} /> Export</button></div>
    </header>
    <div className="mobile-tabs"><button className={mobileTab==='model'?'active':''} onClick={() => setMobileTab('model')}><Move3D size={15}/>Model</button><button className={mobileTab==='chat'?'active':''} onClick={() => setMobileTab('chat')}><MessageCircle size={15}/>Chat</button><button className={mobileTab==='details'?'active':''} onClick={() => setMobileTab('details')}><Layers2 size={15}/>Details</button></div>
    <div className="workspace-body">
      <aside className={`chat-panel ${leftOpen?'':'collapsed'}`}>
        <div className="panel-heading"><div><span className="eyebrow muted">YOUR DESIGN PARTNER</span><h3>Shape the idea</h3></div><button className="icon-button" title="Collapse conversation" onClick={() => setLeftOpen(false)}><PanelLeftClose size={16}/></button></div>
        <div className="conversation">
          <div className="assistant-intro"><span className="assistant-icon"><Sparkles size={16}/></span><div><b>Let’s make it real.</b><p>Describe what you have in mind. I’ll turn it into a design you can shape and inspect.</p></div></div>
          {conversations.map((message, i) => <div className={`chat-message ${message.role}`} key={`${i}-${message.content}`}><span className="message-role">{message.role==='user'?'YOU':'FOLDSPEC'}</span><p>{message.content}</p></div>)}
          {busy && <div className="thinking"><span className="thinking-dots"><i/><i/><i/></span><span>Working through the details</span></div>}
          {proposal && <div className="proposal-card"><div className="proposal-title"><Sparkles size={14}/>DESIGN PROPOSAL</div><p>{proposal.message}</p>{proposal.questions.length > 0 && <div className="question-list">{proposal.questions.map((q) => <div key={q}><Circle size={7} fill="currentColor"/>{q}</div>)}</div>}{proposal.proposed_changes.length>0 && <div className="proposal-changes">{proposal.proposed_changes.map((c)=><span key={c}><Check size={13}/>{c}</span>)}</div>}{proposal.spec && <div className="proposal-actions"><button className="button ghost" onClick={() => setProposal(null)}>Keep current</button><button className="button primary" onClick={() => void applySpec(proposal.spec!)}>Apply changes <ArrowRight size={14}/></button></div>}</div>}
          {error && <div className="alert error"><AlertTriangle size={15}/>{error}</div>}
        </div>
        <form className="chat-compose" onSubmit={(e) => { e.preventDefault(); void sendMessage() }}><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={aiReady ? 'Tell me what to change…' : healthError ? 'Start the local server to enable chat…' : 'Add your OpenRouter key to enable chat…'} aria-label="Describe a change" rows={2}/><div className="compose-footer"><span>{aiReady ? 'OPENROUTER READY' : 'AI UNAVAILABLE · FORMS STILL WORK'}</span><button className="send-button" type="submit" aria-label="Send message" disabled={!aiReady || busy || !prompt.trim()}><Send size={16}/></button></div></form>
        {!leftOpen && <button className="expand-panel left-expand" title="Expand conversation" onClick={() => { setLeftOpen(true); setMobileTab('chat') }}><PanelLeftOpen size={17}/></button>}
      </aside>
      <section className="model-panel">
        <div className="model-topline"><div className="breadcrumb"><span>{LABELS[project.spec.template_id]}</span><ChevronRight size={13}/><span className="muted">Design preview</span></div><span className={`manufacturing-badge ${build?.evidence_status==='validated'?'validated':'experimental'}`}><span/>{build?.evidence_status==='validated'?'Validated design':'Experimental design'}</span></div>
        <div className="viewport-wrap"><Suspense fallback={<div className="build-overlay"><span className="spinner"/><span>Loading the model inspector</span></div>}><ModelCanvas url={modelUrl(project)} mode={mode} cameraKind={cameraKind} cameraPreset={cameraPreset} boundsMm={build?.bounds_mm} resetKey={cameraReset} features={features} selectedFeature={selectedFeature} onSelect={() => setSelectedFeature('overall')} onFeatureSelect={setSelectedFeature} /></Suspense>
          <div className="viewport-title"><span>3D MODEL <i/> PREVIEW REVISION {build?.revision ?? project.revision}{build && build.revision !== project.revision && <b> · REQUESTED {project.revision}</b>}</span><button className="viewport-capture" title="Fit model to view" onClick={() => { setCameraPreset('iso'); setCameraReset((value) => value + 1) }}><Focus size={15}/></button></div>
          {showDimensions && build?.bounds_mm && <div className="model-dimension-card"><span className="dim-card-label">OVERALL SIZE <i/> {units.toUpperCase()}</span><div>{Object.entries(build.bounds_mm).map(([k,v])=><span key={k}><b>{(v/factor).toFixed(1)}</b><small>{k}</small></span>)}</div></div>}
          <div className="view-cube"><span>ORIENTATION</span><div className="cube-cross"><button title="Top view" onClick={()=>setCameraPreset('top')}>↑</button><button title="Left view" onClick={()=>setCameraPreset('left')}>←</button><button title="Front view" onClick={()=>setCameraPreset('front')}>●</button><button title="Right view" onClick={()=>setCameraPreset('right')}>→</button><button title="Bottom view" onClick={()=>setCameraPreset('bottom')}>↓</button></div><button className="cube-back" title="Back view" onClick={()=>setCameraPreset('back')}>BACK</button></div>
          <div className="viewport-toolbar"><button className="toolbar-select" title="Isometric view" onClick={()=>setCameraPreset('iso')}><Move3D size={16}/><span>Isometric</span><ChevronDown size={12}/></button><span className="toolbar-sep"/><button title="Perspective or orthographic camera" className="camera-toggle" onClick={()=>setCameraKind(cameraKind==='perspective'?'orthographic':'perspective')}>{cameraKind==='perspective'?'PERSPECTIVE':'ORTHOGRAPHIC'}</button><span className="toolbar-sep"/><button className={mode==='shaded'?'tool-active':''} title="Shaded mode" onClick={()=>setMode('shaded')}><Circle size={16}/></button><button className={mode==='edges'?'tool-active':''} title="Show edges" onClick={()=>setMode('edges')}><Grid2X2 size={16}/></button><button className={mode==='translucent'?'tool-active':''} title="Translucent inspection" onClick={()=>setMode('translucent')}><Layers2 size={16}/></button><span className="toolbar-sep"/><button className={showDimensions?'tool-active':''} title="Toggle measurements" onClick={()=>setShowDimensions(!showDimensions)}>{showDimensions?<Eye size={16}/>:<EyeOff size={16}/>}</button><button title="Fullscreen" onClick={() => { if (document.fullscreenElement) void document.exitFullscreen(); else void workspaceRef.current?.requestFullscreen() }}><Crosshair size={16}/></button></div>
          {building && <div className="build-overlay updating"><span className="spinner"/><span>Updating your model</span><small>Revision {project.revision} · showing last successful preview</small></div>}
          {selected && selected.id!=='overall' && <div className="selection-chip"><span className="tiny-green"/>{selected.label}<small>{prettyFeature(selected, factor, units)}</small></div>}
          {!build && <div className="build-overlay"><span className="spinner"/><span>Preparing your first model</span></div>}
        </div>
        <div className="model-footer"><span><i className="footer-led"/>MODEL STATUS <b>{build?.geometry_status==='valid'?'SOLID READY':building?'REBUILDING':'WAITING'}</b></span><span className="footer-coords">X <i/> Y <i/> Z <i/></span><span className="model-footer-right"><ShieldCheck size={14}/> SINGLE SOLID</span></div>
      </section>
      <aside className={`details-panel ${rightOpen?'':'collapsed'}`}>
        <div className="detail-title"><div><span className="eyebrow muted">PART INSPECTOR</span><h3>Design details</h3></div><button className="icon-button" title="Collapse details" onClick={() => setRightOpen(false)}><PanelRightClose size={16}/></button></div>
        <div className="detail-tabs">{(['dimensions','features','checks'] as const).map((tab)=><button key={tab} className={rightTab===tab?'active':''} onClick={()=>setRightTab(tab)}>{tab}{tab==='checks'&&build?.findings.some(f=>f.severity==='error')?<span className="tab-alert"/>:null}</button>)}</div>
        {rightTab==='dimensions' && <div className="details-content"><div className="section-caption">PRIMARY DIMENSIONS <span>{units.toUpperCase()} <ChevronDown size={11}/></span></div>{Object.entries(project.spec.parameters).map(([key,value])=><label className="dimension-input" key={key}><span>{key.replaceAll('_',' ')}<small>{['inside_radius','flange_height'].includes(key)?'REFERENCE':''}</small></span><div><input type="number" min="1" step="0.1" defaultValue={(value/factor).toFixed(1)} key={`${project.revision}-${key}-${units}`} onBlur={(e)=>{const n=Number(e.currentTarget.value);if(Number.isFinite(n)&&n>0&&Math.abs(n-value/factor)>.0001)updateField(key,n)}} onKeyDown={(e)=>{if(e.key==='Enter')e.currentTarget.blur()}}/><span>{units}</span></div></label>)}
          <div className="section-caption features-caption">HOLES & CUTOUTS <button title="Add center hole" onClick={addHole}><Plus size={14}/> ADD HOLE</button></div>{project.spec.holes.length===0 ? <div className="empty-feature">No cutouts yet. Add a hole to get started.</div> : project.spec.holes.map((hole,i)=><button key={i} className={`feature-row ${selectedFeature===`hole:${i+1}`?'selected':''}`} onClick={()=>setSelectedFeature(`hole:${i+1}`)}><span className="feature-icon hole-icon"><Circle size={16}/></span><span><b>Hole {String(i+1).padStart(2,'0')}</b><small>Ø {(hole.diameter/factor).toFixed(1)} {units} <i>·</i> x {(hole.x/factor).toFixed(1)}, y {(hole.y/factor).toFixed(1)}</small></span><MoreHorizontal size={15}/></button>)}
          {(project.spec.slots.length+project.spec.cutouts.length)>0 && [...project.spec.slots.map((x,i)=>({id:`slot:${i+1}`,kind:'Slot',x})),...project.spec.cutouts.map((x,i)=>({id:`cutout:${i+1}`,kind:'Cutout',x}))].map((x)=><button key={x.id} className="feature-row" onClick={()=>setSelectedFeature(x.id)}><span className="feature-icon"><Square size={15}/></span><span><b>{x.kind}</b><small>Feature detail</small></span><MoreHorizontal size={15}/></button>)}
          <div className="inspector-note"><Info size={14}/><p>Edits save as a new revision. All measurements update in the model preview.</p></div></div>}
        {rightTab==='features' && <div className="details-content"><div className="section-caption">GEOMETRY FEATURES <span>{features.length} TOTAL</span></div>{features.map((f)=><button key={f.id} className={`feature-row ${selectedFeature===f.id?'selected':''}`} onClick={()=>setSelectedFeature(f.id)}><span className={`feature-icon ${f.kind==='hole'?'hole-icon':''}`}>{f.kind==='hole'?<Circle size={16}/>:f.kind==='bend'?<RotateCcw size={15}/>:<Square size={15}/>}</span><span><b>{f.label}</b><small>{prettyFeature(f,factor,units)||f.kind}</small></span><ChevronRight size={15}/></button>)}<div className="inspector-note"><Info size={14}/><p>Select a feature to inspect its dimensions. Select the model to clear the selection.</p></div></div>}
        {rightTab==='checks' && <div className="details-content"><div className="section-caption">MANUFACTURING CHECKS <span>{build?.findings.length ?? 0} ITEMS</span></div>{build?.findings.map((finding)=><button key={finding.id} className={`check-row ${finding.severity}`} onClick={()=>finding.feature_id&&setSelectedFeature(finding.feature_id)}><span className="check-icon">{finding.severity==='pass'?<Check size={15}/>:finding.severity==='unknown'?<Info size={15}/>:<AlertTriangle size={15}/>}</span><span><b>{finding.title}</b><small>{finding.detail}</small></span>{finding.feature_id&&<ChevronRight size={14}/>}</button>)}<div className="validation-banner"><div><AlertTriangle size={15}/><b>Experimental export</b></div><p>Supplier rules and physical fit need review before production.</p></div></div>}
        {!rightOpen && <button className="expand-panel right-expand" title="Expand details" onClick={() => { setRightOpen(true); setMobileTab('details') }}><PanelRightOpen size={17}/></button>}
      </aside>
    </div>
  </main>
}
