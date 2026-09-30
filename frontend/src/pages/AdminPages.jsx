import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, Check, ChevronDown, ChevronLeft, ChevronRight, CircleAlert, Clock3, Database, FileText, ListFilter, Plus, RefreshCw, Search, Shield, ShieldCheck, Sparkles, UserCheck, UserPlus, UsersRound, Workflow, XCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { adminApi, healthApi } from '../api/endpoints'
import { errorMessage } from '../api/client'
import { Badge, Button, Card, EmptyState, ErrorState, Field, LoadingState, Modal, PageHeader } from '../components/UI'

const emailDomainFixes = { 'gmai.com': 'gmail.com', 'gmial.com': 'gmail.com', 'gamil.com': 'gmail.com', 'gmail.con': 'gmail.com' }
function suggestedEmail(value) {
  const at = value.lastIndexOf('@')
  if (at < 1) return null
  const domain = value.slice(at + 1).toLowerCase()
  const correction = emailDomainFixes[domain]
  return correction ? `${value.slice(0, at + 1)}${correction}` : null
}

export default function AdminPages({ page }) {
  if (page === 'hr') return <HrAccounts />
  if (page === 'audit') return <AuditLogs />
  if (page === 'health') return <SystemHealth />
  if (page === 'pipeline') return <QueryPipeline />
  return <Analytics overview={page === 'overview'} />
}

const PIPELINE_PAGE_SIZE = 25
const pipelineIcons = [Search, Database, ListFilter, Workflow, ShieldCheck, Check]
function QueryPipeline() {
  const [pageData, setPageData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  async function load() {
    setLoading(true); setError('')
    try {
      const { data } = await adminApi.searches(PIPELINE_PAGE_SIZE, offset)
      setPageData(data)
      setSelectedId((current) => data.items.some((item) => item.id === current) ? current : data.items[0]?.id || null)
    } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [offset])
  const items = pageData?.items || []
  const filtered = items.filter((item) => `${item.query_text} ${item.id}`.toLowerCase().includes(filter.toLowerCase()))
  const selected = filtered.find((item) => item.id === selectedId) || filtered[0] || null
  const stages = selected?.pipeline?.stages || []
  const hasNext = Boolean(pageData && offset + pageData.limit < pageData.total)
  return <div className="page-wrap admin-dashboard query-pipeline-page">
    <PageHeader eyebrow="SYSTEM CONSOLE · QUERY TRACE" title="Search pipeline" description="Inspect how each saved hiring query moved through requirement parsing, retrieval, reranking, evidence analysis, and final ranking." action={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh traces</Button>} />
    {error && <ErrorState error={error} retry={load} />}
    {loading && !pageData ? <LoadingState label="Loading recorded query traces…" /> : pageData && <>
      <div className="pipeline-summary-bar"><span><Workflow size={16} /> Persisted search traces</span><strong>{pageData.total.toLocaleString()} queries</strong><small>Showing {pageData.total ? offset + 1 : 0}–{Math.min(offset + pageData.limit, pageData.total)} · newest first</small></div>
      {!pageData.total ? <Card><EmptyState title="No query traces yet" text="Admin traces will appear after candidate searches are completed." /></Card> : <div className="pipeline-browser">
        <Card className="pipeline-query-list"><div className="pipeline-list-head"><div><span className="eyebrow">SAVED QUERIES</span><strong>{pageData.total.toLocaleString()}</strong></div><label className="table-search"><Search size={14} /><input aria-label="Filter this page of queries" placeholder="Filter this page" value={filter} onChange={(e) => setFilter(e.target.value)} /></label></div>
          {filtered.length ? <div className="pipeline-query-items">{filtered.map((item) => <button type="button" key={item.id} className={`pipeline-query-row ${selected?.id === item.id ? 'selected' : ''}`} onClick={() => setSelectedId(item.id)}><span className="pipeline-query-text">{item.query_text || 'Query text unavailable'}</span><span className="pipeline-query-meta"><time>{new Date(item.created_at).toLocaleString()}</time><span>Top {item.top_n_requested}</span><span>{item.candidate_pool_size} retrieved</span></span></button>)}</div> : <EmptyState title="No queries match" text="Try another phrase from this page." />}
          <div className="pipeline-pagination"><button type="button" className="button button-secondary" disabled={!offset || loading} onClick={() => setOffset(Math.max(0, offset - PIPELINE_PAGE_SIZE))}><ChevronLeft size={15} /> Previous</button><span>Page {Math.floor(offset / PIPELINE_PAGE_SIZE) + 1} of {Math.max(1, Math.ceil(pageData.total / pageData.limit))}</span><button type="button" className="button button-secondary" disabled={!hasNext || loading} onClick={() => setOffset(offset + PIPELINE_PAGE_SIZE)}>Next <ChevronRight size={15} /></button></div>
        </Card>
        {selected && <section className="pipeline-detail-column" aria-label="Selected query details"><Card className="pipeline-selected-query"><div className="pipeline-query-heading"><div><span className="eyebrow">SELECTED SEARCH · TOP {selected.top_n_requested}</span><h2>{selected.query_text || 'Query text unavailable'}</h2><small>{new Date(selected.created_at).toLocaleString()} · ID <code>{selected.id}</code></small></div><Badge tone={selected.fallback_used ? 'amber' : 'mint'}>{selected.fallback_used ? 'Fallback used' : selected.processing_mode || 'Completed'}</Badge></div><div className="pipeline-facts"><PipelineFact label="Resumes considered" value={selected.resumes_considered} icon={Database} /><PipelineFact label="Candidates retrieved" value={selected.candidate_pool_size} icon={Search} /><PipelineFact label="Search latency" value={selected.processing_time_ms == null ? 'Not recorded' : `${Math.round(selected.processing_time_ms)} ms`} icon={Clock3} /></div>{selected.fallback_reason && <div className="pipeline-fallback-note"><CircleAlert size={16} /><span><strong>Fallback detail</strong>{selected.fallback_reason}</span></div>}</Card>
          <Card className="pipeline-trace-card"><div className="card-topline"><div><span className="eyebrow">RECORDED EXECUTION</span><h2>Query processing stages</h2></div><Badge>{stages.length ? `${stages.length} stages` : 'Trace unavailable'}</Badge></div>
            {stages.length ? <ol className="pipeline-stage-list">{stages.map((stage, index) => { const Icon = pipelineIcons[index] || Activity; return <motion.li key={stage.id} className="pipeline-stage" initial={{ opacity: 0, y: 9 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .07, duration: .22 }}><div className="pipeline-stage-icon"><Icon size={16} /></div><div className="pipeline-stage-content"><div className="pipeline-stage-heading"><div><span className="pipeline-stage-index">0{index + 1}</span><h3>{stage.label}</h3></div><span className="pipeline-duration">{stage.duration_ms == null ? 'Timing unavailable' : `${stage.duration_ms < 1 ? '<1' : Math.round(stage.duration_ms)} ms`}</span></div><div className="pipeline-stage-details">{Object.entries(stage.details || {}).filter(([key]) => key !== 'timings_ms' && key !== 'agents').map(([key, value]) => <span key={key}><small>{key.replaceAll('_', ' ')}</small><strong>{formatPipelineValue(value)}</strong></span>)}</div>{stage.details?.agents?.length > 0 && <div className="pipeline-agent-list">{stage.details.agents.map((agent) => <span key={agent}><Check size={12} /> {agent}</span>)}</div>}{stage.details?.timings_ms && <div className="pipeline-subtimings">{Object.entries(stage.details.timings_ms).map(([name, duration]) => <span key={name}>{name.replaceAll('_', ' ')} <b>{duration < 1 ? '<1' : Math.round(duration)} ms</b></span>)}</div>}</div><span className="pipeline-stage-state"><Check size={14} /> Complete</span></motion.li> })}</ol> : <EmptyState title="Detailed trace not available" text="This search predates stage-level timing capture. New completed searches will include stage timings and retrieval counts." />}
          </Card>
          <GuardrailSummary summary={selected.guardrails} />
          <ProviderTrace providers={selected.providers || selected.retrieval_meta?.providers} />
        </section>}
      </div>}
    </>}
  </div>
}

function PipelineFact({ label, value, icon: Icon }) { return <div className="pipeline-fact"><span><Icon size={15} /> {label}</span><strong>{value ?? '-'}</strong></div> }
function formatPipelineValue(value) {
  if (value == null || value === '') return 'Not available'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'None'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
function ProviderTrace({ providers = {} }) {
  const entries = Object.entries(providers)
  return <Card className="pipeline-provider-card"><div className="card-topline"><div><span className="eyebrow">MODEL PROVIDERS</span><h2>Provider and fallback details</h2></div><Sparkles size={17} /></div>{entries.length ? <div className="pipeline-provider-list">{entries.map(([name, info]) => { const fallback = Boolean(info?.fallback_used); const names = info?.provider ? [info.provider] : info?.providers || []; const reasons = info?.fallback_reason ? [info.fallback_reason] : info?.fallback_reasons || []; return <div className="pipeline-provider-row" key={name}><span className={`pipeline-provider-indicator ${fallback ? 'fallback' : ''}`} /><div><strong>{name.replaceAll('_', ' ')}</strong><small>{names.length ? names.join(', ') : 'Provider name not recorded'}</small>{reasons.map((reason, i) => <small className="pipeline-provider-reason" key={i}>{reason}</small>)}</div><Badge tone={fallback ? 'amber' : 'mint'}>{fallback ? 'Fallback' : 'Primary path'}</Badge></div> })}</div> : <p className="muted">Provider details were not stored for this search.</p>}</Card>
}

function GuardrailSummary({ summary }) {
  const data = summary || {}
  const candidateCount = data.candidate_count || 0
  const needsReview = (data.flagged_candidates || 0) > 0 || (data.validation_warnings || 0) > 0 || (data.matched_requirements_without_evidence || 0) > 0
  const status = !candidateCount ? 'No candidate results' : needsReview ? 'Review recommended' : 'No issues recorded'
  const tone = !candidateCount ? 'neutral' : needsReview ? 'amber' : 'mint'
  return <Card className="pipeline-guardrail-card">
    <div className="card-topline"><div><span className="eyebrow">EVIDENCE VALIDATION</span><h2>Guardrail outcomes</h2></div><Badge tone={tone}>{status}</Badge></div>
    <p className="pipeline-guardrail-intro">Existing explainability checks record whether matched requirements are supported by resume evidence and flag unsupported or contradictory claims.</p>
    <div className="pipeline-guardrail-grid">
      <PipelineFact label="Candidates checked" value={data.candidate_count} icon={UsersRound} />
      <PipelineFact label="Validated" value={data.validated_candidates} icon={ShieldCheck} />
      <PipelineFact label="Flagged" value={data.flagged_candidates} icon={CircleAlert} />
      <PipelineFact label="Validation warnings" value={data.validation_warnings} icon={Shield} />
      <PipelineFact label="Matched requirements" value={data.matched_requirements} icon={Check} />
      <PipelineFact label="Without evidence" value={data.matched_requirements_without_evidence} icon={FileText} />
    </div>
    {candidateCount > 0 && <p className="pipeline-guardrail-footnote">{data.matched_requirements_with_evidence || 0} of {data.matched_requirements || 0} matched requirements have linked evidence.</p>}
  </Card>
}

function Analytics({ overview }) {
  const [data, setData] = useState(null), [metrics, setMetrics] = useState(null), [error, setError] = useState('')
  async function load() { setError(''); try { const [a, m] = await Promise.all([adminApi.analytics(), adminApi.retrievalMetrics()]); setData(a.data); setMetrics(m.data) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  const chartData = useMemo(() => (metrics || []).slice().reverse().map((x, i) => ({ index: i + 1, pool: x.candidate_pool_size, considered: x.resumes_considered })), [metrics])
  if (!data && !error) return <LoadingState />
  return <div className="page-wrap admin-dashboard">
    <PageHeader eyebrow={overview ? 'SYSTEM CONSOLE · OVERVIEW' : 'SYSTEM CONSOLE · ANALYTICS'} title={overview ? 'Platform overview' : 'System analytics'} description="Operational signals from persisted platform activity. Counts reflect the current database snapshot." action={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh data</Button>} />
    {error && <ErrorState error={error} retry={load} />}
    {data && <>
      <section className="admin-section" aria-labelledby="resume-ops-title">
        <div className="section-heading"><div><span className="eyebrow">PROCESSING PIPELINE</span><h2 id="resume-ops-title">Resume operations</h2></div><span>Current database snapshot</span></div>
        <div className="admin-metrics admin-metrics-core">
          <AdminMetric label="Total resumes" value={data.total_resumes} icon={FileText} />
          <AdminMetric label="Processed" value={data.processed_resumes} icon={Check} tone="mint" />
          <AdminMetric label="In progress" value={data.pending_resumes} icon={Activity} tone="amber" />
          <AdminMetric label="Partially processed" value={data.partial_resumes} icon={Activity} />
          <AdminMetric label="Failed" value={data.failed_resumes} icon={CircleAlert} tone="rose" />
        </div>
      </section>
      <section className="admin-section" aria-labelledby="retrieval-title">
        <div className="section-heading"><div><span className="eyebrow">RECRUITING ACTIVITY</span><h2 id="retrieval-title">Search and platform signals</h2></div><span>Up to 100 recent retrieval records</span></div>
        <div className="admin-analytics-grid">
          <Card className="chart-card admin-retrieval-card">
            <div className="card-topline"><div><span className="eyebrow">RETRIEVAL VOLUME</span><h2>Candidate pool and resumes considered</h2></div><Badge>Persisted searches</Badge></div>
            {chartData.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}><defs><linearGradient id="poolFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a494ef" stopOpacity={.22} /><stop offset="100%" stopColor="#a494ef" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#303a50" vertical={false} /><XAxis dataKey="index" tickLine={false} axisLine={false} tick={{ fill: '#929eb4', fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#929eb4', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#171e2e', border: '1px solid #394662', borderRadius: 12, color: '#edf2fb' }} /><Area type="monotone" dataKey="pool" name="Candidate pool" stroke="#b4a5ff" fill="url(#poolFill)" /><Area type="monotone" dataKey="considered" name="Resumes considered" stroke="#8caeff" fill="none" /></AreaChart></ResponsiveContainer></div> : <EmptyState title="No retrieval records" text="Retrieval metrics will appear after candidate searches have been recorded." />}
          </Card>
          <Card className="admin-side-card admin-signals-card">
            <span className="eyebrow">PLATFORM INVENTORY</span><h2>Workspace signals</h2>
            <div className="admin-signal-list">
              <div><span><UsersRound size={15} /> Candidates indexed</span><strong>{data.total_candidates}</strong></div>
              <div><span><Search size={15} /> Recorded searches</span><strong>{data.total_searches}</strong></div>
              <div><span><UserCheck size={15} /> Active HR accounts</span><strong>{data.active_hr_users} <small>/ {data.total_hr_users}</small></strong></div>
              <div><span><RefreshCw size={15} /> Fallback usage</span><strong>{(data.fallback_usage_rate * 100).toFixed(1)}%</strong></div>
            </div>
            <div className="admin-side-divider" />
            <span className="eyebrow">SHORTLIST PREFERENCES</span>
            <div className="topn-stat"><span className="topn-ring"><strong>{data.total_searches ? Math.round(data.top3_searches * 100 / data.total_searches) : 0}%</strong></span><div><strong>Top 3</strong><span>{data.top3_searches} recorded searches</span></div></div>
            <div className="topn-stat"><span className="topn-ring violet"><strong>{data.total_searches ? Math.round(data.top5_searches * 100 / data.total_searches) : 0}%</strong></span><div><strong>Top 5</strong><span>{data.top5_searches} recorded searches</span></div></div>
            <div className="admin-latency"><span>Average search latency</span><strong>{data.avg_search_latency_ms == null ? 'Not available' : `${Math.round(data.avg_search_latency_ms)} ms`}</strong></div>
            <p className="muted">Fallback rate and latency come from stored search records, not live provider probes.</p>
          </Card>
        </div>
      </section>
    </>}
  </div>
}function AdminMetric({ label, value, icon: Icon, tone = '' }) { return <Card className="admin-metric"><div className={`admin-metric-icon ${tone}`}><Icon size={17} /></div><span>{label}</span><strong>{value ?? '-'}</strong></Card> }

function HrAccounts() {
  const [rows, setRows] = useState(null), [error, setError] = useState(''), [show, setShow] = useState(false), [confirm, setConfirm] = useState(null), [form, setForm] = useState({ email: '', full_name: '', phone: '', temporary_password: '' }), [busy, setBusy] = useState(false), [notice, setNotice] = useState(''), [filter, setFilter] = useState('')
  async function load() { setError(''); try { const { data } = await adminApi.hrUsers(); setRows(data) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  async function create(e) { e.preventDefault(); const correction = suggestedEmail(form.email); if (correction) { setError(`Check the email domain. Did you mean ${correction}-`); return } setBusy(true); setError(''); try { await adminApi.createHr({ ...form, phone: form.phone || null, temporary_password: form.temporary_password || null }); setNotice('HR account created. They will be asked to set a new password at first sign-in.'); setForm({ email: '', full_name: '', phone: '', temporary_password: '' }); setShow(false); await load() } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  async function changeStatus() { if (!confirm) return; setBusy(true); try { await adminApi.status(confirm.id, !confirm.is_active); setNotice(`${confirm.full_name} ${confirm.is_active ? 'disabled' : 'enabled' }.`); setConfirm(null); await load() } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  const shown = (rows || []).filter((u) => `${u.full_name} ${u.email}`.toLowerCase().includes(filter.toLowerCase()))
  return <div className="page-wrap"><PageHeader eyebrow="ACCESS CONTROL · HR MANAGEMENT" title="HR accounts" description="Provision recruiting access and manage account status. Changes are applied by the backend immediately." action={<Button onClick={() => setShow(true)}><UserPlus size={16} /> Create HR account</Button>} />{notice && <div className="success-banner"><Check size={15} />{notice}</div>}{error && <ErrorState error={error} retry={load} />}{!rows && !error ? <LoadingState /> : <Card className="data-table-card"><div className="table-head"><div><span className="eyebrow">RECRUITER ACCESS</span><h2>HR users <span className="count-tag">{rows?.length || 0}</span></h2></div><label className="table-search"><Search size={15} /><input placeholder="Find a recruiter" value={filter} onChange={(e) => setFilter(e.target.value)} /></label></div>{shown.length ? <div className="table-scroll"><table><thead><tr><th>Recruiter</th><th>Phone</th><th>Last sign-in</th><th>Status</th><th>Joined</th><th></th></tr></thead><tbody>{shown.map((u) => <tr key={u.id}><td><div className="table-person"><div className="mini-avatar">{u.full_name.slice(0, 1)}</div><span><strong>{u.full_name}</strong><small>{u.email}</small></span></div></td><td>{u.phone || '—'}</td><td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}</td><td><Badge tone={u.is_active ? 'mint' : 'rose'}>{u.is_active ? 'Active' : 'Disabled'}</Badge></td><td>{new Date(u.created_at).toLocaleDateString()}</td><td><Button variant="quiet" onClick={() => setConfirm(u)}>{u.is_active ? 'Disable' : 'Enable'}</Button></td></tr>)}</tbody></table></div> : <EmptyState title="No HR accounts found" text={filter ? 'Try a different name or email.' : 'Create the first recruiting account to get started.'} />}</Card>}
    {show && <Modal title="Create HR account" onClose={() => setShow(false)}><form className="modal-form" onSubmit={create}><Field label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /><Field label="Work email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />{suggestedEmail(form.email) && <p className="email-correction" role="alert">Check the domain: did you mean <strong>{suggestedEmail(form.email)}</strong>?</p>}<Field label="Phone (optional)" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /><Field label="Temporary password (optional)" type="password" minLength={8} hint="Leave blank to let the backend generate one." value={form.temporary_password} onChange={(e) => setForm({ ...form, temporary_password: e.target.value })} /><div className="modal-actions"><Button type="button" variant="quiet" onClick={() => setShow(false)}>Cancel</Button><Button loading={busy}><UserPlus size={15} /> Create account</Button></div></form></Modal>}{confirm && <Modal title={`${confirm.is_active ? 'Disable' : 'Enable'} account?`} onClose={() => setConfirm(null)}><p className="modal-copy">{confirm.is_active ? `${confirm.full_name} will no longer be able to sign in.` : `${confirm.full_name} will regain sign-in access.`}</p><div className="modal-actions"><Button variant="quiet" onClick={() => setConfirm(null)}>Cancel</Button><Button variant={confirm.is_active ? 'danger' : 'primary'} loading={busy} onClick={changeStatus}>{confirm.is_active ? 'Disable account' : 'Enable account'}</Button></div></Modal>}</div>
}

function AuditLogs() {
  const emptyFilters = { q: '', action: '', resource_type: '', user_id: '', from_date: '', to_date: '' }
  const [filters, setFilters] = useState(emptyFilters), [applied, setApplied] = useState(emptyFilters)
  const [result, setResult] = useState(null), [error, setError] = useState(''), [offset, setOffset] = useState(0)
  const pageSize = 25
  async function load(nextOffset = offset, currentFilters = applied) {
    setError('')
    try {
      const params = Object.fromEntries(Object.entries({ ...currentFilters, limit: pageSize, offset: nextOffset }).filter(([, value]) => value !== ''))
      const { data } = await adminApi.audit(params)
      setResult(data)
    } catch (e) { setError(errorMessage(e)) }
  }
  useEffect(() => { load(offset, applied) }, [offset, applied])
  function applyFilters(event) { event.preventDefault(); setOffset(0); setApplied({ ...filters }) }
  function clearFilters() { setFilters(emptyFilters); setOffset(0); setApplied(emptyFilters) }
  const items = result?.items || []
  const page = Math.floor(offset / pageSize) + 1
  const pageCount = Math.max(1, Math.ceil((result?.total || 0) / pageSize))
  return <div className="page-wrap"><PageHeader eyebrow="GOVERNANCE - AUDIT TRAIL" title="Audit logs" description="Timestamped HR and administrator activity, including candidate data access, exports, shortlist changes, and email delivery." action={<Button variant="secondary" onClick={() => load()}><RefreshCw size={15} /> Refresh</Button>} />{error && <ErrorState error={error} retry={() => load()} />}{!result && !error ? <LoadingState /> : <Card className="data-table-card"><div className="table-head"><div><span className="eyebrow">FILTERED ACTIVITY</span><h2>Activity record <span className="count-tag">{result?.total || 0}</span></h2></div></div><form className="audit-filters" onSubmit={applyFilters}><label className="table-search"><Search size={15} /><input placeholder="Search actor, action, resource, IP" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} /></label><select aria-label="Action" value={filters.action} onChange={(e) => setFilters({ ...filters, action: e.target.value })}><option value="">All actions</option>{(result?.actions || []).map((x) => <option key={x} value={x}>{x.replaceAll('_', ' ')}</option>)}</select><select aria-label="Resource type" value={filters.resource_type} onChange={(e) => setFilters({ ...filters, resource_type: e.target.value })}><option value="">All resources</option>{(result?.resource_types || []).map((x) => <option key={x} value={x}>{x.replaceAll('_', ' ')}</option>)}</select><select aria-label="Actor" value={filters.user_id} onChange={(e) => setFilters({ ...filters, user_id: e.target.value })}><option value="">All users</option>{(result?.users || []).map((x) => <option key={x.id} value={x.id}>{x.name} ({x.email})</option>)}</select><label className="audit-date">From<input type="date" value={filters.from_date} onChange={(e) => setFilters({ ...filters, from_date: e.target.value })} /></label><label className="audit-date">To<input type="date" value={filters.to_date} onChange={(e) => setFilters({ ...filters, to_date: e.target.value })} /></label><Button type="submit"><Search size={14} /> Apply</Button><Button type="button" variant="quiet" onClick={clearFilters}>Clear</Button></form>{items.length ? <div className="table-scroll"><table><thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Resource</th><th>Resource ID</th><th>Details</th></tr></thead><tbody>{items.map((x) => <tr key={x.id}><td>{new Date(x.created_at).toLocaleString()}</td><td><span className="table-person"><span><strong>{x.user_name || 'System / unknown'}</strong><small>{x.user_email || x.ip_address || x.user_id || '-'}</small></span></span></td><td><Badge>{x.action.replaceAll('_', ' ')}</Badge></td><td>{x.resource_type || '-'}</td><td><code>{x.resource_id || '-'}</code></td><td><code>{Object.keys(x.details || {}).length ? JSON.stringify(x.details) : '-'}</code></td></tr>)}</tbody></table></div> : <EmptyState title="No matching events" text="Adjust the filters or date range and try again." />}<div className="audit-pagination"><span>Showing {result?.total ? offset + 1 : 0} to {Math.min(offset + items.length, result?.total || 0)} of {result?.total || 0}</span><div><Button variant="quiet" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</Button><span>Page {page} of {pageCount}</span><Button variant="quiet" disabled={offset + pageSize >= (result?.total || 0)} onClick={() => setOffset(offset + pageSize)}>Next</Button></div></div></Card>}</div>
}

function SystemHealth() {
  const [health, setHealth] = useState(null), [readiness, setReadiness] = useState(null), [liveness, setLiveness] = useState(null), [error, setError] = useState('')
  async function load() { try { const [{ data }, { data: ready }, { data: live }] = await Promise.all([adminApi.health(), healthApi.ready(), healthApi.live()]); setHealth(data); setReadiness(ready); setLiveness(live) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  if (!health && !error) return <LoadingState />
  const degraded = health && (health.database !== 'ok' || health.redis !== 'ok' || health.celery !== 'ok')
  return <div className="page-wrap health-page"><PageHeader eyebrow="OPERATIONS · SYSTEM HEALTH" title="System health" description="Service checks and configured provider names reported by the backend. Provider names are not availability checks." action={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh checks</Button>} />{error && <ErrorState error={error} retry={load} />}{health && <><Card className="health-banner"><span className={`health-emblem ${degraded ? 'degraded' : 'healthy'}`}>{degraded ? <CircleAlert size={20} /> : <Check size={20} />}</span><div><span className="eyebrow">OVERALL STATUS</span><h2>{degraded ? 'Service degradation detected' : 'Core services responding'}</h2><p>Database, Redis, and Celery checks from the last request.</p></div><Badge tone={degraded ? 'rose' : 'mint'}>{degraded ? 'Degraded' : 'Healthy'}</Badge></Card><section className="health-services" aria-label="Service checks"><div className="health-section-heading"><div><span className="eyebrow">SERVICE CHECKS</span><h2>Connected services</h2></div><span>Status from latest refresh</span></div><div className="health-grid"><HealthCard name="API liveness" value={liveness?.status || 'Unknown'} icon={Activity} unknown={!liveness} /><HealthCard name="API readiness" value={readiness?.status || 'Unknown'} icon={Activity} unknown={!readiness} /><HealthCard name="Database" value={health.database} icon={Database} /><HealthCard name="Redis" value={health.redis} icon={Activity} /><HealthCard name="LLM provider" value={health.llm_provider} configured /><HealthCard name="Embedding provider" value={health.embedding_provider} configured /><HealthCard name="Reranker provider" value={health.reranker_provider} configured /><HealthCard name="Celery worker" value={health.celery} /></div></section><div className="inline-note"><CircleAlert size={15} /> Celery is healthy only when a worker responds to the broker health check.</div></>}</div>
}
function HealthCard({ name, value, icon: Icon = Activity, configured, unknown }) { const healthy = ['ok', 'ready', 'alive'].includes(value); const tone = unknown ? 'neutral' : configured ? 'violet' : healthy ? 'mint' : 'rose'; return <Card className="health-card"><div className={`health-card-icon ${tone}`}><Icon size={17} /></div><div><span>{name}</span><strong>{value}</strong></div><Badge tone={tone}>{unknown ? 'Unknown' : configured ? 'Configured' : healthy ? 'Healthy' : value === 'unavailable' || value === 'not_ready' ? 'Unavailable' : value}</Badge></Card> }
