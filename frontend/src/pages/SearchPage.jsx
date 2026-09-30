import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Activity, ArrowRight, BookmarkCheck, Check, ChevronDown, CircleHelp, Download, Eye, FileSearch, FileText, GitCompareArrows, LoaderCircle, MapPin, Search, SlidersHorizontal, Sparkles, Target, UserRound, X } from 'lucide-react'
import { motion } from 'framer-motion'
import { searchApi, resumeApi, jobApi } from '../api/endpoints'
import { errorMessage } from '../api/client'
import { toast } from '../components/ToastViewport'
import { Badge, Button, Card, EmptyState, ErrorState, Field, PageHeader, ScoreRing } from '../components/UI'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [jobId, setJobId] = useState('')
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsError, setJobsError] = useState('')
  const [topN, setTopN] = useState(5)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState([])
  const [candidate, setCandidate] = useState(null)
  const [skillFilter, setSkillFilter] = useState('')
  const [minExperience, setMinExperience] = useState('')
  const [sortBy, setSortBy] = useState('rank')
  const [minFilterYears, setMinFilterYears] = useState(''), [maxFilterYears, setMaxFilterYears] = useState('')
  const [filterSkills, setFilterSkills] = useState(''), [filterEducation, setFilterEducation] = useState(''), [filterCertifications, setFilterCertifications] = useState('')
  const [requirementDraft, setRequirementDraft] = useState([]), [savingRequirements, setSavingRequirements] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    const candidateId = new URLSearchParams(location.search).get('candidate')
    if (candidateId) resumeApi.candidate(candidateId).then(({ data: full }) => setCandidate(full)).catch((e) => setError(errorMessage(e)))
  }, [location.search])
  useEffect(() => {
    let active = true
    jobApi.list().then(({ data: rows }) => { if (active) setJobs(rows) })
      .catch((e) => { if (active) setJobsError(errorMessage(e)) })
      .finally(() => { if (active) setJobsLoading(false) })
    return () => { active = false }
  }, [])
  const selectedBrief = jobs.find((job) => job.id === jobId)
  const tokens = (value) => value.split(',').map((part) => part.trim()).filter(Boolean)
  useEffect(() => {
    if (!selectedBrief) { setRequirementDraft([]); return }
    setRequirementDraft([...(selectedBrief.mandatory_requirements || []).map((item) => ({ ...item, priority: 'mandatory' })), ...(selectedBrief.preferred_requirements || []).map((item) => ({ ...item, priority: 'preferred' }))])
  }, [selectedBrief?.id])
  async function saveRequirements() {
    if (!jobId) return
    setSavingRequirements(true)
    try {
      const { data: updated } = await jobApi.updateRequirements(jobId, requirementDraft.filter((item) => item.value.trim()).map((item) => ({ requirement_type: item.type, priority: item.priority, value: item.value.trim() })))
      setJobs((items) => items.map((item) => item.id === updated.id ? updated : item))
      toast.success('Job requirements saved. They will guide the next search.')
    } catch (err) { toast.error(errorMessage(err)) } finally { setSavingRequirements(false) }
  }
  async function exportSelected(format) {
    if (!data?.search_id || !selected.length) return
    try {
      const { data: blob, headers } = await searchApi.exportShortlist(data.search_id, { candidate_ids: selected, format })
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      const disposition = headers?.['content-disposition'] || ''
      const fileName = disposition.match(/filename="?([^";]+)"?/)?.[1] || `shortlist.${format === 'pdf' ? 'pdf' : 'csv'}`
      link.href = url; link.download = fileName; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast.success(`${selected.length} selected candidate${selected.length === 1 ? '' : 's'} exported.`)
    } catch (err) { toast.error(errorMessage(err)) }
  }
  async function run(e) {
    e.preventDefault(); if (!query.trim() && !jobId) { setError('Describe your hiring requirements or select a saved job brief.'); return }
    setLoading(true); setError(''); setData(null); setSelected([])
    try { const { data: result } = await searchApi.create({ query_text: query.trim() || null, job_description_id: jobId.trim() || null, top_n: topN, candidate_filters: { min_experience_years: minFilterYears === '' ? null : Number(minFilterYears), max_experience_years: maxFilterYears === '' ? null : Number(maxFilterYears), skills: tokens(filterSkills), education: tokens(filterEducation), certifications: tokens(filterCertifications) } }); setData(result); toast.success(`Search complete. ${result.results?.length || 0} candidates returned.`) } catch (err) { setError(errorMessage(err)) } finally { setLoading(false) }
  }
  function toggle(id) { setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : s.length < 5 ? [...s, id] : s) }
  function compare() { sessionStorage.setItem('ri_compare', JSON.stringify({ search_id: data.search_id, candidate_ids: selected })); navigate('/compare') }
  const visibleResults = (data?.results || []).filter((item) => (minExperience === '' || (item.years_of_experience ?? 0) >= Number(minExperience)) && (!skillFilter.trim() || `${item.matched_requirements.map((x) => x.requirement).join(' ')} ${item.relevant_projects.map((x) => `${x.name} ${(x.technologies || []).join(' ')}`).join(' ')}`.toLowerCase().includes(skillFilter.toLowerCase()))).slice().sort((a, b) => sortBy === 'score' ? b.final_score - a.final_score : sortBy === 'experience' ? (b.years_of_experience || 0) - (a.years_of_experience || 0) : a.rank - b.rank)
  return <div className="page-wrap search-page">
    <PageHeader eyebrow="CANDIDATE INTELLIGENCE Â· SEARCH" title="Find your next great hire" description="Search in natural language. Every shortlist comes with requirement-level evidence you can inspect." />
    <Card className="search-composer"><div className="composer-heading"><div className="composer-badge"><Sparkles size={18} /></div><div><strong>Describe who you're looking for</strong><span>Use a job brief or tell us what matters in plain language.</span></div><span className="composer-secure">Evidence grounded</span></div>
      <form onSubmit={run}><label className="search-input-wrap"><span className="prompt-mark" aria-hidden="true"><Sparkles size={16} /></span><textarea aria-label="Additional hiring requirements" placeholder="Add or refine requirements, e.g. prioritize candidates who have mentored a team. You can also search with only a saved brief." value={query} onChange={(e) => setQuery(e.target.value)} rows={3} /><button className="clear-input" type="button" onClick={() => setQuery('')} aria-label="Clear requirements"><X size={16} /></button></label>
        <details open className="selected-brief-preview advanced-filters"><summary><SlidersHorizontal size={14} /> Advanced candidate filters · optional, applied before retrieval</summary><div className="advanced-filter-grid"><label className="field compact"><span>Min. experience years</span><input type="number" min="0" step="0.5" value={minFilterYears} onChange={(e) => setMinFilterYears(e.target.value)} placeholder="Any" /></label><label className="field compact"><span>Max. experience years</span><input type="number" min="0" step="0.5" value={maxFilterYears} onChange={(e) => setMaxFilterYears(e.target.value)} placeholder="Any" /></label><label className="field compact"><span>Skills (comma separated)</span><input value={filterSkills} onChange={(e) => setFilterSkills(e.target.value)} placeholder="Python, React" /></label><label className="field compact"><span>Education</span><input value={filterEducation} onChange={(e) => setFilterEducation(e.target.value)} placeholder="Bachelor's, Computer Science" /></label><label className="field compact"><span>Certifications</span><input value={filterCertifications} onChange={(e) => setFilterCertifications(e.target.value)} placeholder="AWS, PMP" /></label></div><small className="field-hint">Comma-separated values are alternatives within each category. Selected categories and experience range are combined.</small></details>
        {selectedBrief && <details className="selected-brief-preview requirement-editor"><summary>Edit hiring requirements · {requirementDraft.length} structured</summary><p>{selectedBrief.raw_text}</p><div className="requirement-editor-list">{requirementDraft.map((item, index) => <div className="requirement-editor-row" key={`${index}-${item.type}`}><select aria-label="Requirement type" value={item.type} onChange={(e) => setRequirementDraft((items) => items.map((row, i) => i === index ? { ...row, type: e.target.value } : row))}><option value="skill">Skill</option><option value="technology">Technology</option><option value="domain">Domain</option><option value="responsibility">Responsibility</option><option value="education">Education</option><option value="certification">Certification</option></select><input aria-label="Requirement" value={item.value} onChange={(e) => setRequirementDraft((items) => items.map((row, i) => i === index ? { ...row, value: e.target.value } : row))} /><select aria-label="Requirement priority" value={item.priority} onChange={(e) => setRequirementDraft((items) => items.map((row, i) => i === index ? { ...row, priority: e.target.value } : row))}><option value="mandatory">Mandatory</option><option value="preferred">Preferred</option></select><button type="button" className="icon-button" aria-label="Remove requirement" onClick={() => setRequirementDraft((items) => items.filter((_, i) => i !== index))}><X size={14} /></button></div>)}<div className="requirement-editor-actions"><button type="button" className="button button-secondary" onClick={() => setRequirementDraft((items) => [...items, { type: 'skill', value: '', priority: 'mandatory' }])}>Add requirement</button><Button type="button" loading={savingRequirements} onClick={saveRequirements}>Save requirements</Button></div></div></details>}
        <div className="composer-controls"><label className="field compact"><span>Saved job brief <CircleHelp size={13} title="Optional. The selected brief is combined with any requirements above." /></span><select aria-label="Saved job brief (optional)" value={jobId} onChange={(e) => setJobId(e.target.value)} disabled={jobsLoading}><option value="">{jobsLoading ? 'Loading job briefsâ€¦' : 'None Â· optional'}</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.title || 'Untitled job brief'}</option>)}</select></label><div className="topn-control"><span>Shortlist size</span><div className="segmented"><button type="button" className={topN === 3 ? 'selected' : ''} onClick={() => setTopN(3)}>Top 3</button><button type="button" className={topN === 5 ? 'selected' : ''} onClick={() => setTopN(5)}>Top 5</button></div></div><Button type="submit" loading={loading} className="search-submit"><FileSearch size={17} /> {loading ? 'Searching intelligenceâ€¦' : 'Find candidates'} <ArrowRight size={16} /></Button></div>
        {jobsError && <small className="field-hint">Saved briefs could not be loaded: {jobsError}</small>}
        {!jobsLoading && !jobsError && jobs.length === 0 && <small className="field-hint">No saved briefs yet. You can search with the requirements above or create one under Job briefs.</small>}
        {selectedBrief && <details className="selected-brief-preview"><summary>Using â€œ{selectedBrief.title || 'Untitled job brief'}â€ Â· view brief and extracted requirements</summary><p>{selectedBrief.raw_text}</p><div className="req-chips">{selectedBrief.mandatory_requirements?.map((r, i) => <Badge tone="mint" key={`m${i}`}>{r.value}</Badge>)}{selectedBrief.preferred_requirements?.map((r, i) => <Badge tone="amber" key={`p${i}`}>{r.value}</Badge>)}</div></details>}
      </form>
      <div className="composer-foot"><span><Check size={13} /> Hybrid search</span><span><Check size={13} /> Cross-encoder reranking</span><span><Check size={13} /> Evidence review</span></div>
      <div className="grounding-note"><Sparkles size={14} /><span><strong>Grounded intelligence</strong><small>Candidate matches include supporting resume sources when available.</small></span></div>
    </Card>
    {error && <ErrorState error={error} retry={data ? undefined : () => setError('')} />}
    {loading && <Card className="search-loading"><div className="search-loader-icon"><LoaderCircle className="spin" size={23} /></div><div><strong>Reading the signal in your brief</strong><p>Retrieving and assessing relevant candidates. A full search can take a minute or two.</p><div className="loading-bars"><i /><i /><i /><i /><i /><i /></div></div></Card>}
    {data && <section className="results-section"><div className="results-heading"><div><div className="eyebrow">SHORTLIST Â· {data.results.length} RESULTS</div><h2>Candidate intelligence</h2><p>{data.resumes_considered} resumes considered Â· {data.processing_time_ms == null ? 'latency unavailable' : `${Math.round(data.processing_time_ms)} ms`} Â· {data.retrieval_method}</p></div><div className="result-actions"><Badge tone={data.fallback_used ? 'amber' : 'mint'}>{data.fallback_used ? 'Fallback used' : 'No fallback reported'}</Badge>{selected.length > 0 && <><Button variant="secondary" onClick={() => { sessionStorage.setItem('ri_shortlist_import', JSON.stringify({ search_id: data.search_id, candidate_ids: selected })); navigate('/shortlists?import=1') }}><BookmarkCheck size={15} /> Save to shortlist</Button><Button variant="secondary" onClick={() => exportSelected('csv')}><Download size={15} /> CSV</Button><Button variant="secondary" onClick={() => exportSelected('pdf')}><Download size={15} /> PDF</Button></>}{selected.length > 1 && <Button variant="secondary" onClick={compare}><GitCompareArrows size={16} /> Compare ({selected.length})</Button>}</div></div><ProviderStatusPanel data={data} /><SearchExplanationPanel data={data} />
      {data.results.length > 0 && <div className="result-filters"><label className="table-search"><Search size={14} /><input aria-label="Filter shortlist by skill" placeholder="Filter this shortlist by skill or project" value={skillFilter} onChange={(e) => setSkillFilter(e.target.value)} /></label><label className="field compact"><span>Min. years</span><input aria-label="Minimum experience" type="number" min="0" step="1" placeholder="Any" value={minExperience} onChange={(e) => setMinExperience(e.target.value)} /></label><label className="field compact"><span>Sort shortlist</span><select value={sortBy} onChange={(e) => setSortBy(e.target.value)}><option value="rank">Backend rank</option><option value="score">Relevance score</option><option value="experience">Experience</option></select></label><span className="filter-note">Filters apply to these {data.results.length} returned candidates.</span></div>}
      {visibleResults.length ? <div className="candidate-list">{visibleResults.map((person, i) => <CandidateCard key={person.candidate_id} item={person} index={i} selected={selected.includes(person.candidate_id)} onToggle={() => toggle(person.candidate_id)} onOpen={async () => { try { const { data: full } = await resumeApi.candidate(person.candidate_id); setCandidate({ ...full, search_result: person }) } catch (e) { setError(errorMessage(e)) } }} />)}</div> : <EmptyState title={data.results.length ? 'No shortlist candidates match these filters' : 'No matches in this result set'} text="Adjust your filters or broaden the role requirements." />}</section>}
    {candidate && <CandidateDrawer candidate={candidate} onClose={() => setCandidate(null)} />}
    {!data && !loading && !error && <div className="search-hint-row"><span className="hint-spark"><Sparkles size={17} /></span><span><strong>Designed for evidence-first decisions</strong><small>See matched, partial, and missing requirements with resume source attribution.</small></span><Link to="/jobs">Build a structured job brief <ArrowRight size={15} /></Link></div>}
  </div>
}

function ProviderStatusPanel({ data }) {
  const providers = Object.entries(data.provider_status || {})
  return <section className="provider-status-panel" aria-label="Search processing status">
    <div className="provider-status-heading"><div><span className="eyebrow">PROCESSING PATH</span><h3>{data.fallback_used ? 'Fallback was used' : 'Primary provider path'}</h3><p>{data.fallback_used ? data.fallback_reason || 'One or more configured providers used a fallback.' : 'Provider and retrieval details reported for this search.'}</p></div><Badge tone={data.fallback_used ? 'amber' : 'mint'}>{data.fallback_used ? 'Fallback' : 'Completed'}</Badge></div>
    {providers.length ? <div className="provider-status-grid">{providers.map(([name, value]) => {
      const details = value && typeof value === 'object' ? value : { provider: String(value) }
      const fallback = Boolean(details.fallback_used) || [details.provider, ...(details.providers || [])].some((item) => String(item).toLowerCase().includes('fallback'))
      const names = details.provider ? [details.provider] : details.providers || []
      const reasons = details.fallback_reason ? [details.fallback_reason] : details.fallback_reasons || []
      return <article className="provider-status-item" key={name}><span className={`provider-status-icon ${fallback ? 'is-fallback' : ''}`}><Activity size={15} /></span><div className="provider-status-copy"><strong>{name.replaceAll('_', ' ')}</strong><span>{names.length ? names.join(', ') : 'Provider detail unavailable'}</span>{reasons.map((reason, index) => <small key={index}>{reason}</small>)}</div><Badge tone={fallback ? 'amber' : 'mint'}>{fallback ? 'Fallback' : 'Primary'}</Badge></article>
    })}</div> : <p className="provider-status-empty">Provider-level details were not recorded for this search.</p>}
  </section>
}

function SearchExplanationPanel({ data }) {
  const stages = data.processing_pipeline?.stages || []
  return <details className="search-explanation" open>
    <summary><span><Sparkles size={15} /> How retrieval and ranking produced this shortlist</span><small>{stages.length} recorded stages</small></summary>
    {stages.length ? <div className="search-pipeline">{stages.map((stage, index) => <article className="search-pipeline-stage" key={stage.id || index}><span className="pipeline-step">{String(index + 1).padStart(2, '0')}</span><div><strong>{stage.label || stage.id}</strong><small>{stage.details?.candidates_loaded != null ? `${stage.details.candidates_loaded} profiles loaded · ${stage.details.candidates_after_filters ?? stage.details.candidates_loaded} passed filters` : Object.entries(stage.details || {}).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' · ') || 'Stage completed'}</small></div><Badge>{stage.duration_ms == null ? 'Recorded' : `${Math.round(stage.duration_ms)} ms`}</Badge></article>)}</div> : <p className="provider-status-empty">Detailed stages were not recorded for this saved search.</p>}
  </details>
}

async function openEvidencePage(evidence) {
  if (!evidence.resume_id || !evidence.page_number || !/\.pdf$/i.test(evidence.source_file || '')) {
    toast.error('A page-specific PDF link is unavailable for this evidence excerpt.')
    return
  }
  const tab = window.open('about:blank', '_blank')
  if (!tab) { toast.error('Allow pop-ups to open the source PDF page.'); return }
  tab.opener = null
  try {
    const { data } = await resumeApi.download(evidence.resume_id)
    const url = URL.createObjectURL(data)
    tab.location.replace(`${url}#page=${Math.max(1, Number(evidence.page_number))}`)
    window.setTimeout(() => URL.revokeObjectURL(url), 10 * 60 * 1000)
  } catch (error) {
    tab.close()
    toast.error(errorMessage(error))
  }
}

export function CandidateCard({ item, index = 0, selected, onToggle, onOpen }) {
  return <motion.article className={`candidate-card ${selected ? 'candidate-selected' : ''}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .055 }}>
    <div className="candidate-rank"><span>0{item.rank}</span><i /></div><div className="candidate-main"><div className="candidate-title-row"><div className="person-avatar">{item.candidate_name?.slice(0, 1)?.toUpperCase() || <UserRound size={20} />}</div><div className="person-title"><h3>{item.candidate_name || 'Candidate'}</h3><span>{item.years_of_experience == null ? 'Experience not available' : `${item.years_of_experience} years experience`}</span></div><div className="score-block"><ScoreRing value={item.final_score} label="match" /><span>ranking score</span></div><button className={`select-candidate ${selected ? 'on' : ''}`} onClick={onToggle} aria-label={selected ? 'Remove from comparison' : 'Add to comparison'} title="Select for comparison">{selected ? <Check size={15} /> : '+'}</button></div>
      <div className="why-box"><span className="why-icon"><Sparkles size={14} /></span><div><strong>Why this candidate</strong><p>{item.why_selected_summary || 'No explanation was returned for this candidate.'}</p></div></div>
      <div className="findings-grid"><RequirementGroup title="Matched" items={item.matched_requirements} tone="mint" /><RequirementGroup title="Partial" items={item.partial_requirements} tone="amber" /><RequirementGroup title="Missing" items={item.missing_requirements} tone="rose" /></div>
      {item.evidence?.length > 0 && <details className="evidence-panel"><summary><span><FileText size={14} /> Evidence from resume</span><Badge>{item.evidence.length} excerpts</Badge></summary><div className="evidence-list">{item.evidence.slice(0, 5).map((e, i) => <blockquote key={i}><p>“{e.evidence_text}”</p><footer>{e.source_file || 'Resume source'}{e.page_number ? ` · Page ${e.page_number}` : ' · Page not provided'}{e.resume_id && e.page_number && /\.pdf$/i.test(e.source_file || '') && <button type="button" className="evidence-open-page" onClick={() => openEvidencePage(e)}>Open this PDF page</button>}</footer></blockquote>)}</div></details>}
      <div className="candidate-bottom"><div className="skill-pills">{Object.entries(item.score_breakdown?.components || {}).slice(0, 3).map(([k, v]) => <Badge key={k}>{k.replaceAll('_', ' ')} Â· {Math.round(v * 100)}</Badge>)}{item.score_breakdown?.mandatory_coverage && <Badge>Mandatory {item.score_breakdown.mandatory_coverage}</Badge>}{item.relevant_projects?.slice(0, 2).map((p) => <Badge key={p.name}><FileText size={11} /> {p.name || 'Project'}</Badge>)}</div><div className="candidate-links"><Badge tone={item.validation_status === 'validated' ? 'mint' : 'amber'}>{item.validation_status || 'Review'}</Badge><button className="text-link" onClick={onOpen}>Full profile <ArrowRight size={14} /></button></div></div>
    </div>
  </motion.article>
}
function RequirementGroup({ title, items = [], tone }) { return <div className={`finding-group finding-${tone}`}><div className="finding-label"><i className={`finding-dot ${tone}`} />{title}<span>{items.length}</span></div>{items.length ? <div className="finding-pills">{items.map((x, i) => <div key={`${x.requirement}-${i}`} className="finding-item" title={x.evidence_text || x.note || ''}>{x.requirement}{x.evidence_text && <small>Resume evidence linked</small>}</div>)}</div> : <span className="finding-none">No {title.toLowerCase()} requirements</span>}</div> }
function CandidateDrawer({ candidate, onClose }) { const match = candidate.search_result; return <div className="drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><motion.aside className="candidate-drawer" initial={{ x: 480 }} animate={{ x: 0 }} exit={{ x: 480 }}><div className="drawer-head"><div><span className="eyebrow">CANDIDATE INTELLIGENCE</span><h2>{candidate.full_name || 'Candidate profile'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close profile"><X size={18} /></button></div><div className="drawer-scroll"><div className="detail-hero"><div className="person-avatar large">{candidate.full_name?.slice(0, 1) || 'C'}</div><div><strong>{candidate.job_titles?.join(' Â· ') || 'Role history not provided'}</strong><span>{candidate.years_of_experience == null ? 'Experience not available' : `${candidate.years_of_experience} years`} Â· {candidate.location || 'Location not provided'}</span></div></div>{candidate.profile_completeness && <ProfileCompleteness data={candidate.profile_completeness} />}{match && <section className="detail-section"><h3>Why this candidate Â· Rank #{match.rank}</h3><p>{match.why_selected_summary || 'No explanation was returned.'}</p><RequirementGroup title="Matched" items={match.matched_requirements} tone="mint" /><RequirementGroup title="Partial" items={match.partial_requirements} tone="amber" /><RequirementGroup title="Missing" items={match.missing_requirements} tone="rose" />{match.evidence?.length > 0 && <div className="drawer-evidence">{match.evidence.map((e, i) => <blockquote key={i}><p>“{e.evidence_text}”</p><footer>{e.source_file || 'Resume source'}{e.page_number ? ` · Page ${e.page_number}` : ' · Page not provided'}{e.resume_id && e.page_number && /\.pdf$/i.test(e.source_file || '') && <button type="button" className="evidence-open-page" onClick={() => openEvidencePage(e)}>Open this PDF page</button>}</footer></blockquote>)}</div>}</section>}{candidate.summary && <section className="detail-section"><h3>Profile summary</h3><p>{candidate.summary}</p></section>}<section className="detail-section"><h3>Skills</h3><div className="tag-cloud">{candidate.technical_skills?.map((x) => <Badge tone="mint" key={x}>{x}</Badge>)}{candidate.soft_skills?.map((x) => <Badge key={x}>{x}</Badge>)}</div></section><section className="detail-section"><h3>Experience</h3>{candidate.experience?.length ? candidate.experience.map((x, i) => <div className="timeline-item" key={i}><i /><strong>{x.title || 'Role'}</strong><span>{x.company || 'Company not listed'} Â· {x.start_date || ''} {x.end_date ? `â€“ ${x.end_date}` : ''}</span></div>) : <p className="muted">Experience details unavailable.</p>}</section><section className="detail-section"><h3>Projects</h3>{candidate.projects?.length ? candidate.projects.map((x, i) => <div className="detail-row" key={i}><FileText size={15} /><div><strong>{x.name || 'Project'}</strong><span>{x.technologies?.join(', ') || 'Technologies not listed'}</span></div></div>) : <p className="muted">No project information provided.</p>}</section><section className="detail-section"><h3>Education & certifications</h3>{candidate.education?.map((x, i) => <div className="detail-row" key={`e${i}`}><Target size={15} /><div><strong>{x.degree || 'Education'}</strong><span>{x.institution || 'Institution not listed'} Â· {x.end_year || ''}</span></div></div>)}{candidate.certifications?.map((x, i) => <Badge key={`c${i}`}>{x.name}</Badge>)}</section><section className="detail-section"><h3>Resume</h3>{candidate.resume_download_url ? <ResumeDownload url={candidate.resume_download_url} /> : <p className="muted">No resume file is attached.</p>}</section></div></motion.aside></div> }
function ProfileCompleteness({ data }) {
  const score = Number(data.score || 0)
  return <section className="profile-completeness" aria-label={`Candidate profile completeness ${score}%`}>
    <div className="profile-completeness-head"><div><span className="eyebrow">PROFILE COMPLETENESS</span><strong>{score}%</strong></div><span>{data.complete_fields} of {data.total_fields} profile areas</span></div>
    <div className="profile-completeness-track" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score}><i style={{ width: `${score}%` }} /></div>
    {data.missing_fields?.length > 0 ? <p>Missing profile details: {data.missing_fields.join(', ')}</p> : <p>Core profile details are complete.</p>}
  </section>
}

function ResumeDownload({ url }) {
  const [downloadBusy, setDownloadBusy] = useState(false)
  const [viewBusy, setViewBusy] = useState(false)
  const resumeId = url.split('/').filter(Boolean).at(-2)
  async function download() {
    setDownloadBusy(true)
    try {
      const { data } = await resumeApi.download(resumeId)
      const objectUrl = URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = 'resume'
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setDownloadBusy(false)
    }
  }
  async function view() {
    const preview = window.open('', '_blank')
    if (!preview) {
      toast.error('Allow pop-ups to view the resume in a new tab.')
      return
    }
    preview.opener = null
    preview.document.title = 'Resume preview'
    preview.document.body.textContent = 'Loading resumeâ€¦'
    setViewBusy(true)
    try {
      const { data } = await resumeApi.download(resumeId)
      const objectUrl = URL.createObjectURL(data)
      preview.location.href = objectUrl
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    } catch (error) {
      preview.close()
      toast.error(errorMessage(error))
    } finally {
      setViewBusy(false)
    }
  }
  return <div className="resume-actions"><Button variant="secondary" loading={downloadBusy} onClick={download}><FileText size={16} /> Download resume</Button><Button variant="quiet" loading={viewBusy} onClick={view}><Eye size={16} /> View Resume</Button></div>
}
