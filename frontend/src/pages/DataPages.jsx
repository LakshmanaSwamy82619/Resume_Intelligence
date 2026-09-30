import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Bell, BookmarkCheck, Check, ChevronLeft, ChevronRight, Clock3, Download, FileText, GitCompareArrows, Mail, Plus, RefreshCw, Save, Search, ShieldCheck, Trash2, UploadCloud, UserRound, X } from 'lucide-react'
import { adminApi, candidateApi, evaluationApi, hrApi, jobApi, notificationApi, profileApi, resumeApi, searchApi, shortlistApi } from '../api/endpoints'
import { useAuth } from '../state/AuthContext'
import { errorMessage } from '../api/client'
import { Badge, Button, Card, EmptyState, ErrorState, Field, LoadingState, Modal, PageHeader, Progress, TextArea } from '../components/UI'
import { toast } from '../components/ToastViewport'

export default function DataPages({ page }) {
  if (page === 'resumes') return <Resumes />
  if (page === 'jobs') return <Jobs />
  if (page === 'compare') return <Compare />
  if (page === 'shortlists') return <Shortlists />
  if (page === 'history') return <History />
  if (page === 'evaluation') return <Evaluation />
  if (page === 'notifications') return <Notifications />
  return <Profile />
}

function Resumes() {
  const navigate = useNavigate()
  const [pageNum, setPageNum] = useState(1), [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [progress, setProgress] = useState(0), [message, setMessage] = useState(''), [job, setJob] = useState(null), [searchInput, setSearchInput] = useState(''), [search, setSearch] = useState(''), [category, setCategory] = useState(''), [status, setStatus] = useState(''), [skill, setSkill] = useState(''), [dragging, setDragging] = useState(false)
  useEffect(() => { const timer = setTimeout(() => { setSearch(searchInput.trim()); setPageNum(1) }, 250); return () => clearTimeout(timer) }, [searchInput])
  async function load() { setError(''); try { const { data: d } = await candidateApi.list(pageNum, 25, { search: search || undefined, category: category || undefined, processing_status: status || undefined, skill: skill.trim() || undefined }); setData(d) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [pageNum, search, category, status, skill])
  useEffect(() => { if (!job || ['completed', 'failed'].includes(job.status)) return; const timer = setInterval(async () => { try { const { data: d } = await resumeApi.jobStatus(job.id); setJob(d); if (['completed', 'failed'].includes(d.status)) load() } catch {} }, 2500); return () => clearInterval(timer) }, [job?.id, job?.status])
  async function upload(files, bulk) { if (!files.length) return; const invalid = [...files].find((file) => !/\.(pdf|docx|txt)$/i.test(file.name)); if (invalid) { setError(`${invalid.name} is not a supported format. Choose PDF, DOCX, or TXT files.`); return } setBusy(true); setProgress(0); setMessage(''); setError(''); try { const result = bulk ? await resumeApi.bulkUpload([...files], (e) => e.total && setProgress(Math.round(e.loaded * 100 / e.total))) : await resumeApi.upload(files[0], (e) => e.total && setProgress(Math.round(e.loaded * 100 / e.total))); setMessage(result.data.message); if (bulk) { const { data: initial } = await resumeApi.jobStatus(result.data.processing_job_id); setJob(initial); if (initial.status === 'completed') load() } else load() } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  const visible = data?.items || []
  return <div className="page-wrap"><PageHeader eyebrow="TALENT DATA · RESUME LIBRARY" title="Resume library" description="Manage uploaded candidate profiles and follow bulk processing as it completes." action={<label className="button button-primary upload-button"><UploadCloud size={16} /> Upload resumes<input type="file" accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" multiple onChange={(e) => { upload(e.target.files, e.target.files.length > 1); e.target.value = '' }} /></label>} />
    <Card className={`upload-drop ${dragging ? 'dragging' : ''}`} onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false) }} onDrop={(e) => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files, e.dataTransfer.files.length > 1) }}><div className="upload-mark"><UploadCloud size={20} /></div><div><strong>Drop resumes here, or choose files</strong><span>PDF, DOCX, or TXT · Single file or batch upload</span></div><label className="button button-secondary">Browse files<input type="file" accept=".pdf,.docx,.txt" multiple onChange={(e) => { upload(e.target.files, e.target.files.length > 1); e.target.value = '' }} /></label></Card>
    {busy && <Card className="upload-progress"><div><strong>Uploading securely</strong><span>{progress}%</span></div><Progress value={progress} /></Card>}{message && <div className="success-banner"><Check size={16} />{message}</div>}{job && <Card className="job-progress"><div className="job-progress-head"><div><span className="eyebrow">BULK PROCESSING</span><h3>Upload status</h3></div><Badge tone={job.status === 'completed' ? 'mint' : job.status === 'failed' ? 'rose' : 'amber'}>{job.status}</Badge></div><Progress value={job.total_items ? (job.processed_items + job.failed_items) * 100 / job.total_items : 0} /><div className="job-counts"><span><b>{job.processed_items}</b> processed</span><span><b>{job.failed_items}</b> failed</span><span><b>{job.duplicate_items}</b> duplicates</span><span><b>{job.total_items}</b> total</span></div></Card>}
      {error && <ErrorState error={error} retry={load} />}
    {!data && !error ? <LoadingState /> : data && <Card className="data-table-card"><div className="table-head"><div><span className="eyebrow">SHARED TALENT POOL</span><h2>Resume profiles <span className="count-tag">{data.total}</span></h2><small className="muted">{data.total} matching profiles · {data.total_resumes} resumes indexed</small></div></div><div className="resume-library-filters"><label className="table-search"><Search size={15} /><input placeholder="Search name, email, filename" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} /></label><label className="field compact"><span>Dataset</span><select value={category} onChange={(e) => { setCategory(e.target.value); setPageNum(1) }}><option value="">All datasets</option>{data.categories?.map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label className="field compact"><span>Processing status</span><select value={status} onChange={(e) => { setStatus(e.target.value); setPageNum(1) }}><option value="">All statuses</option>{data.processing_statuses?.map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label className="field compact"><span>Skill in resume</span><input placeholder="e.g. Python" value={skill} onChange={(e) => { setSkill(e.target.value); setPageNum(1) }} /></label></div>{visible.length ? <div className="table-scroll"><table><thead><tr><th>Candidate</th><th>Experience</th><th>Skills</th><th>Dataset / resume</th><th>Status</th><th>Profile completeness</th><th>Candidate ID</th><th></th></tr></thead><tbody>{visible.map((x) => <tr key={x.candidate_id}><td><div className="table-person"><div className="mini-avatar">{x.full_name?.slice(0, 1) || 'C'}</div><span><strong>{x.full_name || 'Candidate'}</strong><small>{x.email || 'Email not provided'}</small></span></div></td><td>{x.years_of_experience == null ? '—' : `${x.years_of_experience} yrs`}</td><td><div className="skill-pills">{x.technical_skills?.slice(0, 4).map((s) => <Badge key={s}>{s}</Badge>)}</div></td><td><strong>{x.category || 'Uncategorized'}</strong><small className="profile-gap-count">{x.source_filename || 'Resume filename unavailable'}{x.resume_count > 1 ? ` · ${x.resume_count} resumes` : ''}</small></td><td><Badge tone={x.processing_status === 'completed' ? 'mint' : x.processing_status === 'failed' ? 'rose' : 'amber'}>{x.processing_status || 'unknown'}</Badge></td><td><span className="badge badge-mint">{x.profile_completeness?.score ?? 0}%</span><small className="profile-gap-count">{x.profile_completeness?.missing_fields?.length || 0} profile gaps</small></td><td><button className="copy-id" title={x.candidate_id} onClick={() => toast.copy(x.candidate_id, 'Candidate ID')}>{x.candidate_id.slice(0, 8)}… <span>Copy</span></button></td><td><button className="table-action" title="Open candidate" onClick={() => navigate(`/search?candidate=${x.candidate_id}`)}><UserRound size={16} /></button></td></tr>)}</tbody></table></div> : <EmptyState title="No resumes match these filters" text="Try changing the dataset, processing status, skill, or search terms." />}
      <div className="pagination"><span>Page {data.page} · {data.total} candidates</span><div><Button variant="quiet" disabled={data.page <= 1} onClick={() => setPageNum(pageNum - 1)}><ChevronLeft size={16} /> Previous</Button><Button variant="quiet" disabled={data.page * data.page_size >= data.total} onClick={() => setPageNum(pageNum + 1)}>Next <ChevronRight size={16} /></Button></div></div></Card>}
  </div>
}

function Shortlists() {
  const location = useLocation()
  const navigate = useNavigate()
  const [shortlists, setShortlists] = useState(null)
  const [activeId, setActiveId] = useState('')
  const [name, setName] = useState('Recruiter shortlist')
  const [selectedIds, setSelectedIds] = useState([])
  const [searchId, setSearchId] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [emailTarget, setEmailTarget] = useState(null)
  const [emailSending, setEmailSending] = useState(false)

  async function load() {
    setError('')
    try {
      const { data } = await shortlistApi.list()
      setShortlists(data)
      setActiveId((current) => current && data.some((item) => item.id === current) ? current : data[0]?.id || '')
    } catch (e) { setError(errorMessage(e)) }
  }
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!new URLSearchParams(location.search).has('import')) return
    try {
      const imported = JSON.parse(sessionStorage.getItem('ri_shortlist_import') || '{}')
      setSearchId(imported.search_id || '')
      setSelectedIds(imported.candidate_ids || [])
      if (imported.search_id) searchApi.get(imported.search_id).then(({ data }) => setSearchResults(data.results || [])).catch((e) => setError(errorMessage(e)))
    } catch { setError('The selected candidates could not be loaded. Return to search and select them again.') }
  }, [location.search])

  async function create(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const { data } = await shortlistApi.create({ name, search_id: searchId || null, candidate_ids: selectedIds })
      sessionStorage.removeItem('ri_shortlist_import')
      setShortlists((items) => [data, ...(items || [])])
      setActiveId(data.id); setName('Recruiter shortlist'); setSelectedIds([])
      toast.success(`Saved ${data.candidates.length} candidate${data.candidates.length === 1 ? '' : 's'} to ${data.name}.`)
      navigate('/shortlists', { replace: true })
    } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }
  async function addSelected() {
    if (!activeId || !selectedIds.length) return
    setLoading(true); setError('')
    try {
      const { data } = await shortlistApi.addCandidates(activeId, { candidate_ids: selectedIds, search_id: searchId || null })
      setShortlists((items) => items.map((item) => item.id === data.id ? data : item)); setSelectedIds([])
      toast.success('Candidates added to the saved shortlist.')
    } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }
  async function removeCandidate(candidateId) {
    if (!activeId) return
    try {
      await shortlistApi.removeCandidate(activeId, candidateId)
      setShortlists((items) => items.map((item) => item.id === activeId ? { ...item, candidates: item.candidates.filter((person) => person.candidate_id !== candidateId) } : item))
      toast.success('Candidate removed from shortlist.')
    } catch (e) { setError(errorMessage(e)) }
  }
  async function deleteList() {
    const active = shortlists?.find((item) => item.id === activeId)
    if (!active || !window.confirm(`Delete “${active.name}” and its saved candidate notes?`)) return
    try { await shortlistApi.remove(activeId); const remaining = shortlists.filter((item) => item.id !== activeId); setShortlists(remaining); setActiveId(remaining[0]?.id || ''); toast.success('Shortlist deleted.') }
    catch (e) { setError(errorMessage(e)) }
  }
  async function saveCandidate(person) {
    try {
      const { data } = await shortlistApi.updateCandidate(activeId, person.candidate_id, { stage: person.stage, notes: person.notes })
      setShortlists((items) => items.map((item) => item.id === data.id ? data : item)); toast.success('Candidate stage and notes saved.')
    } catch (e) { setError(errorMessage(e)) }
  }
  async function sendCandidateEmail() {
    if (!activeId || !emailTarget || emailSending) return
    setEmailSending(true)
    try {
      await shortlistApi.updateCandidate(activeId, emailTarget.candidate_id, { stage: emailTarget.stage, notes: emailTarget.notes || null })
      await shortlistApi.emailCandidate(activeId, emailTarget.candidate_id)
      toast.success(`Email sent to ${emailTarget.email}.`)
      setEmailTarget(null)
    } catch (e) { setError(errorMessage(e)) }
    finally { setEmailSending(false) }
  }
  async function rename(active, nextName) {
    try {
      const { data } = await shortlistApi.rename(active.id, nextName)
      setShortlists((items) => items.map((item) => item.id === data.id ? data : item)); toast.success('Shortlist renamed.')
    } catch (e) { setError(errorMessage(e)) }
  }
  function toggleCandidate(id) { setSelectedIds((ids) => ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]) }
  const active = shortlists?.find((item) => item.id === activeId)
  const savedCandidateCount = new Set((shortlists || []).flatMap((item) => (item.candidates || []).map((person) => person.candidate_id))).size
  const alreadySaved = new Set(active?.candidates.map((person) => person.candidate_id) || [])

  return <div className="page-wrap">
    <PageHeader eyebrow="RECRUITING · SHORTLISTS" title="Persistent recruiter shortlists" description="Save candidates across sessions, track their recruiting stage, and keep recruiter notes with each profile." action={<Button variant="secondary" onClick={load}><RefreshCw size={15} /> Refresh</Button>} />
    {error && <ErrorState error={error} retry={load} />}
    {location.search.includes('import=1') && <Card className="shortlist-import-card"><div className="card-topline"><div><span className="eyebrow">SAVE SEARCH SELECTION</span><h2>{selectedIds.length} selected candidates</h2></div><Badge tone="mint">{searchResults.length} results in search</Badge></div>
      {searchResults.length > 0 && <fieldset className="compare-candidate-picker"><legend>Choose candidates from this saved search</legend>{searchResults.map((person) => <label className="compare-candidate-option" key={person.candidate_id}><input type="checkbox" checked={selectedIds.includes(person.candidate_id)} onChange={() => toggleCandidate(person.candidate_id)} /><span><strong>{person.candidate_name || 'Candidate'}</strong><small>Rank #{person.rank} · {Math.round(person.final_score * 100)}% match</small></span></label>)}</fieldset>}
      <form className="shortlist-create-form" onSubmit={create}><Field label="Shortlist name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={160} /><Button loading={loading} disabled={!selectedIds.length}><BookmarkCheck size={15} /> Create shortlist</Button>{active && selectedIds.length > 0 && <Button type="button" variant="secondary" loading={loading} onClick={addSelected}>Add to “{active.name}”</Button>}</form>
    </Card>}
    {!shortlists && !error ? <LoadingState /> : shortlists && <div className="shortlists-layout"><Card className="shortlist-list-panel"><div className="card-topline"><div><span className="eyebrow">SAVED BY YOU ? {shortlists.length} SHORTLIST{shortlists.length === 1 ? "" : "S"}</span><h2>My shortlists</h2></div><Badge title="Unique candidate profiles across saved shortlists">{savedCandidateCount}</Badge></div>{shortlists.length ? shortlists.map((item) => <button className={`history-item ${activeId === item.id ? 'active' : ''}`} key={item.id} onClick={() => setActiveId(item.id)}><span className="history-mark"><BookmarkCheck size={15} /></span><span className="history-copy"><strong>{item.name}</strong><small>{item.candidates.length} candidates · updated {new Date(item.updated_at).toLocaleDateString()}</small></span></button>) : <EmptyState title="No saved shortlists yet" text="Select candidates in search and choose Save to shortlist." />}</Card>
      <Card className="shortlist-detail-panel">{active ? <><div className="card-topline"><div><span className="eyebrow">PERSISTENT SHORTLIST</span><h2>{active.name}</h2><p>{active.candidates.length} candidates · created {new Date(active.created_at).toLocaleDateString()}</p></div><div className="result-actions"><Button variant="secondary" onClick={() => { const next = window.prompt('Rename shortlist', active.name); if (next?.trim()) rename(active, next.trim()) }}><Save size={14} /> Rename</Button><Button variant="danger" onClick={deleteList}><Trash2 size={14} /> Delete</Button></div></div>
        {active.candidates.length ? <div className="shortlist-saved-candidates">{active.candidates.map((person) => <article className="shortlist-saved-person" key={person.candidate_id}><div className="shortlist-person-header"><div className="mini-avatar">{person.full_name?.slice(0, 1) || 'C'}</div><div className="shortlist-person-name"><strong>{person.full_name || 'Candidate'}</strong><small>{person.email || 'Email not provided'} · {person.years_of_experience == null ? 'Experience n/a' : `${person.years_of_experience} years`}</small></div><Badge tone={person.profile_completeness?.score >= 70 ? 'mint' : 'amber'}>Profile {person.profile_completeness?.score ?? 0}%</Badge><button className="table-action" title="Open candidate profile" onClick={() => navigate(`/search?candidate=${person.candidate_id}`)}><UserRound size={15} /></button><button className="table-action" title="Remove candidate" onClick={() => removeCandidate(person.candidate_id)}><X size={15} /></button></div>
          {person.profile_completeness?.missing_fields?.length > 0 && <p className="profile-missing-fields">Profile gaps: {person.profile_completeness.missing_fields.join(', ')}</p>}
          <div className="shortlist-person-edit"><label className="field compact"><span>Recruiting stage</span><select value={person.stage === 'interview' ? 'accepted' : person.stage} onChange={(e) => setShortlists((items) => items.map((item) => item.id === activeId ? { ...item, candidates: item.candidates.map((candidate) => candidate.candidate_id === person.candidate_id ? { ...candidate, stage: e.target.value } : candidate) } : item))}><option value="saved">Saved</option><option value="screening">Screening</option><option value="accepted">Accepted</option><option value="offer">Offer</option><option value="hired">Hired</option><option value="rejected">Rejected</option></select></label><label className="field"><span>Recruiter notes</span><textarea rows={2} maxLength={4000} placeholder="Add interview notes or follow-up context" value={person.notes || ''} onChange={(e) => setShortlists((items) => items.map((item) => item.id === activeId ? { ...item, candidates: item.candidates.map((candidate) => candidate.candidate_id === person.candidate_id ? { ...candidate, notes: e.target.value } : candidate) } : item))} /></label><div className="shortlist-person-actions"><Button variant="secondary" onClick={() => saveCandidate(person)}><Save size={14} /> Save notes</Button>{person.stage !== 'saved' && <Button className="shortlist-send-email" variant="primary" disabled={!person.email} title={!person.email ? 'No email address found on the resume' : undefined} onClick={() => setEmailTarget({ ...person, stage: person.stage === 'interview' ? 'accepted' : person.stage })}><Mail size={14} /> Send email</Button>}</div></div>
        </article>)}</div> : <EmptyState title="This shortlist is empty" text="Save candidates from search to build it." />}</> : <EmptyState title="Choose a shortlist" text="Select a saved list or create one from a search result." />}</Card></div>}
    {emailTarget && <Modal title="Confirm candidate email" onClose={() => !emailSending && setEmailTarget(null)}><div className="shortlist-email-confirm"><span className="shortlist-email-icon"><Mail size={20} /></span><p>Send a <strong>{emailTarget.stage}</strong> update to <strong>{emailTarget.full_name || 'this candidate'}</strong>?</p><div className="shortlist-email-recipients"><span>To</span><strong>{emailTarget.email}</strong>{active?.email_cc && <><span>CC</span><strong>{active.email_cc}</strong></>}</div><p className="muted">The message content will match the candidate’s current recruiting stage.</p><div className="modal-actions"><Button type="button" variant="quiet" disabled={emailSending} onClick={() => setEmailTarget(null)}>Cancel</Button><Button type="button" loading={emailSending} onClick={sendCandidateEmail}><Mail size={15} /> {emailSending ? 'Sending email' : 'Confirm and send'}</Button></div></div></Modal>}
  </div>
}

function Jobs() {
  const [raw, setRaw] = useState(''), [title, setTitle] = useState(''), [mode, setMode] = useState('pasted'), [file, setFile] = useState(null), [job, setJob] = useState(null), [foundJob, setFoundJob] = useState(null), [lookupId, setLookupId] = useState(''), [loading, setLoading] = useState(false), [error, setError] = useState('')
  async function submit(e) { e.preventDefault(); if (mode === 'uploaded' && !file) { setError('Choose a PDF, DOCX, or TXT job description to upload.'); return } setLoading(true); setError(''); try { const { data } = mode === 'uploaded' ? await jobApi.upload(file, title || null) : await jobApi.create({ raw_text: raw, title: title || null, input_mode: mode }); setJob(data); toast.success('Job brief created and saved.') } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) } }
  async function lookup(e) { e.preventDefault(); setLoading(true); setError(''); setFoundJob(null); try { const { data } = await jobApi.get(lookupId.trim()); setFoundJob(data); toast.success('Saved job brief opened.') } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) } }
  return <div className="page-wrap"><PageHeader eyebrow="ROLE DESIGN · JOB BRIEFS" title="Shape the role before the search" description="Create a structured hiring brief from pasted text, an uploaded file, or natural-language requirements." />{error && <ErrorState error={error} retry={() => setError('')} />}<div className="jobs-grid"><Card className="job-editor"><div className="card-topline"><div><span className="eyebrow">NEW JOB BRIEF</span><h2>Hiring context</h2></div><div className="quiet-count">Saved per recruiter</div></div><form onSubmit={submit}><Field label="Job title" placeholder="e.g. Senior Platform Engineer" value={title} onChange={(e) => setTitle(e.target.value)} /><div className="field"><span>Input style</span><div className="segmented wide"><button type="button" className={mode === 'pasted' ? 'selected' : ''} onClick={() => setMode('pasted')}>Job description</button><button type="button" className={mode === 'uploaded' ? 'selected' : ''} onClick={() => setMode('uploaded')}>Upload file</button><button type="button" className={mode === 'natural_language' ? 'selected' : ''} onClick={() => setMode('natural_language')}>Natural language</button><button type="button" className={mode === 'structured' ? 'selected' : ''} onClick={() => setMode('structured')}>Structured</button></div></div>{mode === 'uploaded' ? <label className="field"><span>Job description file</span><input type="file" accept=".pdf,.docx,.txt" required onChange={(e) => setFile(e.target.files?.[0] || null)} /><small className="field-hint">PDF, DOCX, or TXT. Filename is retained for traceability.</small>{file && <small>{file.name} - {(file.size / 1024).toFixed(0)} KB</small>}</label> : <TextArea label="Requirements and role context" placeholder="Paste a job description or describe the role, required skills, preferred experience, qualifications, and project context…" value={raw} onChange={(e) => setRaw(e.target.value)} rows={10} required minLength={10} />}<div className="form-foot"><span>{mode === 'uploaded' ? 'PDF, DOCX, or TXT' : `${raw.length} characters ? At least 10`}</span><Button type="submit" loading={loading}><Plus size={16} /> Create job brief</Button></div></form><div className="inline-note"><ShieldCheck size={15} /> LLM enrichment status is returned by the service. Review extracted requirements before relying on them.</div></Card>
      <div className="job-side"><Card className="job-lookup"><span className="eyebrow">OPEN A SAVED BRIEF</span><h3>Have a job brief ID?</h3><form onSubmit={lookup}><Field label="Job brief ID" placeholder="Paste the ID from a created brief" value={lookupId} onChange={(e) => setLookupId(e.target.value)} required /><Button variant="secondary" loading={loading}>Open brief</Button></form>{foundJob && <div className="found-job"><strong>{foundJob.title || 'Untitled brief'}</strong><span>{foundJob.mandatory_requirements.length} required · {foundJob.preferred_requirements.length} preferred</span><small>{foundJob.llm_enrichment_used ? 'LLM enrichment used' : 'No LLM enrichment recorded'}</small>{foundJob.source_filename && <small>Source file: {foundJob.source_filename}</small>}<code>{foundJob.id}</code></div>}</Card><Card className="job-guide"><span className="guide-icon"><FileText size={18} /></span><h3>A useful brief has signal</h3><p>Include the work the person will do, the skills they need on day one, and what strong evidence looks like.</p><div className="guide-list"><span><i>01</i> Required skills & proficiency</span><span><i>02</i> Scope and years of experience</span><span><i>03</i> Preferred skills and context</span></div></Card>{job && <Card className="created-job"><div className="job-created-top"><span className="created-check"><Check size={16} /></span><Badge tone={job.llm_enrichment_used ? 'mint' : 'amber'}>{job.llm_enrichment_used ? 'LLM enriched' : 'No LLM enrichment'}</Badge></div><h3>{job.title || 'Untitled job brief'}</h3>{job.source_filename && <small className="muted">Uploaded from {job.source_filename}</small>}<p>{job.raw_text.slice(0, 210)}{job.raw_text.length > 210 ? '…' : ''}</p><div className="job-id-row"><span>JOB BRIEF ID</span><code>{job.id}</code><button onClick={() => toast.copy(job.id, 'Job brief ID')}>Copy ID</button></div><div className="req-chips">{job.mandatory_requirements?.map((r, i) => <Badge tone="mint" key={`m${i}`}>{r.value}</Badge>)}{job.preferred_requirements?.map((r, i) => <Badge tone="amber" key={`p${i}`}>{r.value}</Badge>)}</div></Card>}</div></div></div>
}

function History() {
  const navigate = useNavigate()
  const [rows, setRows] = useState(null), [error, setError] = useState(''), [selected, setSelected] = useState(null), [detail, setDetail] = useState(null), [evaluation, setEvaluation] = useState(null)
  async function load() { try { const { data } = await searchApi.history(50); setRows(data) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  useEffect(() => { const id = new URLSearchParams(window.location.search).get('search'); if (id) open(id) }, [])
  async function open(id) { setSelected(id); setDetail(null); setEvaluation(null); try { const [{ data }, { data: review }] = await Promise.all([searchApi.get(id), hrApi.evaluation(id)]); setDetail(data); setEvaluation(review) } catch (e) { setError(errorMessage(e)) } }
  return <div className="page-wrap"><PageHeader eyebrow="RECRUITING ACTIVITY · HISTORY" title="Search history" description="Revisit the exact query, shortlist, provider status, and evidence returned by a previous search." />{error && <ErrorState error={error} retry={load} />}{!rows && !error ? <LoadingState /> : rows?.length ? <div className="history-layout"><Card className="history-list">{rows.map((s) => <button className={`history-item ${selected === s.id ? 'active' : ''}`} key={s.id} onClick={() => open(s.id)}><span className="history-mark"><Search size={15} /></span><span className="history-copy"><strong>{s.query_text}</strong><small>{new Date(s.created_at).toLocaleString()}</small></span><Badge tone={s.fallback_used ? 'amber' : 'mint'}>{s.fallback_used ? 'Fallback' : `Top ${s.top_n_requested}`}</Badge></button>)}</Card><Card className="history-detail">{detail ? <><div className="card-topline"><div><span className="eyebrow">SEARCH DETAIL</span><h2>Shortlist returned</h2></div><Badge>{detail.processing_time_ms == null ? 'Timing n/a' : `${Math.round(detail.processing_time_ms)} ms`}</Badge></div><div className="history-meta"><span><b>{detail.resumes_considered}</b> resumes considered</span><span><b>{detail.candidate_pool_size}</b> in candidate pool</span><span><b>{detail.retrieval_method}</b> retrieval</span></div>{evaluation && <div className="history-evaluation"><div><span className="eyebrow">EVIDENCE COVERAGE</span><strong>{evaluation.evidence_coverage.coverage_rate == null ? 'Not available' : `${(evaluation.evidence_coverage.coverage_rate * 100).toFixed(0)}%`}</strong><small>{evaluation.evidence_coverage.matched_requirements_with_evidence} of {evaluation.evidence_coverage.total_matched_requirements} matched requirements carry evidence</small></div><div><span className="eyebrow">PROVIDER PATH</span><strong>{evaluation.fallback_status.fallback_used ? 'Fallback used' : 'No fallback recorded'}</strong><small>{evaluation.fallback_status.fallback_reason || evaluation.fallback_status.ai_provider || 'Provider details not recorded'}</small></div></div>}<div className="candidate-list compact-list">{detail.results?.map((r) => <div className="history-candidate" key={r.candidate_id}><div className="mini-avatar">{r.rank}</div><div><strong>{r.candidate_name || 'Candidate'}</strong><span>{r.why_selected_summary}</span></div><Badge tone="mint">{Math.round(r.final_score * 100)}%</Badge></div>)}</div><button className="button button-secondary" onClick={() => { sessionStorage.setItem('ri_compare', JSON.stringify({ search_id: detail.search_id, candidate_ids: detail.results.map((x) => x.candidate_id) })); navigate('/compare') }}>Review shortlist in compare <GitCompareArrows size={15} /></button></> : <EmptyState title="Choose a search" text="Select an item to review its candidates and retrieval details." />}</Card></div> : <EmptyState title="No search history yet" text="Candidate searches you run will be saved here." />}</div>
}

function Compare() {
  const location = useLocation()
  const stored = useMemo(() => {
    try { return JSON.parse(sessionStorage.getItem('ri_compare') || '{}') }
    catch { return {} }
  }, [location.key])
  const [searchId, setSearchId] = useState(stored.search_id || '')
  const [candidateIds, setCandidateIds] = useState(stored.candidate_ids || [])
  const [searchDetail, setSearchDetail] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [shortlistLoading, setShortlistLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [reloadHistory, setReloadHistory] = useState(0)
  const [reloadShortlist, setReloadShortlist] = useState(0)

  useEffect(() => {
    let current = true
    setHistoryLoading(true)
    searchApi.history(50)
      .then(({ data }) => { if (current) setHistory(data) })
      .catch((e) => { if (current) setError(errorMessage(e)) })
      .finally(() => { if (current) setHistoryLoading(false) })
    return () => { current = false }
  }, [reloadHistory])

  useEffect(() => {
    if (!searchId) {
      setSearchDetail(null)
      return undefined
    }
    let current = true
    setShortlistLoading(true)
    setError('')
    searchApi.get(searchId)
      .then(({ data }) => {
        if (!current) return
        setSearchDetail(data)
        const available = new Set((data.results || []).map((candidate) => candidate.candidate_id))
        setCandidateIds((selected) => [...new Set(selected)].filter((id) => available.has(id)).slice(0, 5))
      })
      .catch((e) => { if (current) { setSearchDetail(null); setError(errorMessage(e)) } })
      .finally(() => { if (current) setShortlistLoading(false) })
    return () => { current = false }
  }, [searchId, reloadShortlist])

  function chooseSearch(id) {
    setSearchId(id)
    setCandidateIds([])
    setResult(null)
    setError('')
  }

  function toggleCandidate(id) {
    setCandidateIds((selected) => selected.includes(id)
      ? selected.filter((candidateId) => candidateId !== id)
      : selected.length < 5 ? [...selected, id] : selected)
    setResult(null)
  }

  async function compare(event) {
    event?.preventDefault()
    if (!searchId || candidateIds.length < 2 || candidateIds.length > 5) return
    setLoading(true)
    setError('')
    try {
      const { data } = await searchApi.compare({ search_id: searchId, candidate_ids: candidateIds })
      setResult(data)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  function retry() {
    if (!searchId) setReloadHistory((value) => value + 1)
    else if (searchDetail && candidateIds.length >= 2) compare()
    else setReloadShortlist((value) => value + 1)
  }
  return <div className="page-wrap">
    <PageHeader eyebrow="DECISION SUPPORT / COMPARISON" title="Compare without a forced winner" description="Choose a saved search, then select candidates from that exact shortlist. Final decisions stay with your recruiting team." />
    {error && <ErrorState error={error} retry={retry} />}
    {historyLoading && <LoadingState label="Loading saved searches..." />}
    <Card className="compare-picker">
      <form onSubmit={compare} className="compare-form">
        <label className="field"><span>Search shortlist</span>
          <select value={searchId} disabled={historyLoading} onChange={(event) => chooseSearch(event.target.value)}>
            <option value="">{historyLoading ? 'Loading saved searches...' : 'Choose a search...'}</option>
            {history.map((item) => <option value={item.id} key={item.id}>{item.query_text.slice(0, 90)} - Top {item.top_n_requested}</option>)}
          </select>
        </label>
        {shortlistLoading && <LoadingState label="Loading candidates from this search..." />}
        {!shortlistLoading && searchDetail && <fieldset className="compare-candidate-picker">
          <legend>Select 2-5 candidates from this shortlist</legend>
          {(searchDetail.results || []).map((candidate) => {
            const checked = candidateIds.includes(candidate.candidate_id)
            const disabled = !checked && candidateIds.length >= 5
            return <div className={`compare-candidate-option ${checked ? 'selected' : ''}`} key={candidate.candidate_id}>
              <label>
                <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleCandidate(candidate.candidate_id)} />
                <span><strong>{candidate.candidate_name || `Candidate #${candidate.rank}`}</strong><small>Rank #{candidate.rank} - {Math.round(candidate.final_score * 100)}% relevance</small></span>
              </label>
              <code title={candidate.candidate_id}>{candidate.candidate_id}</code>
            </div>
          })}
          {!searchDetail.results?.length && <p className="muted">This search has no saved candidate results.</p>}
        </fieldset>}
        <div className="compare-submit-row">
          <span>{candidateIds.length < 2 ? 'Select at least 2 candidates to compare.' : `${candidateIds.length} of 5 candidates selected.`}</span>
          <Button loading={loading} disabled={candidateIds.length < 2 || candidateIds.length > 5 || !searchId || shortlistLoading}><GitCompareArrows size={16} /> Compare candidates</Button>
        </div>
      </form>
      <small>Candidate IDs are loaded from the selected saved search, so only members of that shortlist can be compared.</small>
    </Card>
    {result && <Card className="comparison-card requirement-matrix-card"><div className="comparison-header"><div><span className="eyebrow">REQUIREMENT MATRIX</span><h2>One screen, requirement by requirement</h2></div><Badge>{result.candidates.length} candidates · {(result.requirements || []).length} requirements</Badge></div><div className="table-scroll comparison-matrix-scroll">{(result.requirements || []).length ? <table className="requirement-matrix"><thead><tr><th>Job requirement</th>{result.candidates.map((person) => <th key={person.candidate_id}><strong>{person.candidate_name || 'Candidate'}</strong><small>Rank #{person.rank} · {Math.round(person.final_score * 100)}%</small></th>)}</tr></thead><tbody>{result.requirements.map((requirement, index) => <tr key={`${requirement.requirement_type || requirement.type}-${requirement.value}-${index}`}><th><span>{requirement.value}</span><small>{requirement.priority || requirement.requirement_type || requirement.type}</small></th>{result.candidates.map((person) => <td key={person.candidate_id}><RequirementCell candidate={person} requirement={requirement} /></td>)}</tr>)}</tbody></table> : <EmptyState title="No structured requirements returned" text="This search did not include structured job requirements to place in the matrix." />}</div><p className="comparison-note">Evidence excerpts link each status to the resume. Scores support review and do not make a hiring decision.</p></Card>}
    {!result && !searchId && !historyLoading && <EmptyState title="Select a shortlist to compare" text="Choose one of your saved searches to see its candidates." />}
  </div>
}
function CompareList({ title, items = [], tone }) { return <div className="compare-list"><div className="compare-list-title"><i className={`finding-dot ${tone}`} />{title}<span>{items.length}</span></div>{items.length ? items.map((x, i) => <div className="compare-finding" key={i}>{x.requirement}<small>{x.evidence_text ? `${x.evidence_text}${x.source_file ? ` · ${x.source_file}` : ''}${x.page_number ? ` · Page ${x.page_number}` : ''}` : x.note || 'No evidence text returned'}</small></div>) : <span className="muted">None returned</span>}</div> }

function RequirementCell({ candidate, requirement }) {
  const normalize = (value) => String(value || '').trim().toLocaleLowerCase()
  const all = [...(candidate.matched_requirements || []).map((item) => ({ ...item, status: 'matched' })), ...(candidate.partial_requirements || []).map((item) => ({ ...item, status: 'partial' })), ...(candidate.missing_requirements || []).map((item) => ({ ...item, status: 'missing' }))]
  const requirementType = requirement.requirement_type || requirement.type
  const match = all.find((item) => normalize(item.requirement) === normalize(requirement.value) && (!item.requirement_type || !requirementType || normalize(item.requirement_type) === normalize(requirementType)))
  return match ? <div className={`matrix-cell matrix-${match.status}`}><Badge tone={match.status === 'matched' ? 'mint' : match.status === 'partial' ? 'amber' : 'rose'}>{match.status}</Badge><small>{match.evidence_text || match.note || (match.status === 'missing' ? 'No supporting evidence found' : 'Evidence details unavailable')}{match.source_file ? ` · ${match.source_file}` : ''}{match.page_number ? ` · p. ${match.page_number}` : ''}</small></div> : <div className="matrix-cell matrix-unassessed"><Badge>Not assessed</Badge><small>No direct requirement finding was returned.</small></div>
}

function Evaluation() {
  const { user } = useAuth()
  const [datasetId, setDatasetId] = useState(''), [dataset, setDataset] = useState(null), [evaluationRequest, setEvaluationRequest] = useState(null), [name, setName] = useState(''), [description, setDescription] = useState(''), [query, setQuery] = useState(''), [candidateId, setCandidateId] = useState(''), [skillStatuses, setSkillStatuses] = useState('{}'), [relevance, setRelevance] = useState(2), [result, setResult] = useState(null), [topN, setTopN] = useState(5), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  async function action(fn) { setError(''); setBusy(true); try { await fn() } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  async function createDataset(e) { e.preventDefault(); await action(async () => { const { data } = await evaluationApi.createDataset({ name, description: description || null }); setDatasetId(data.id); setName(''); await loadDataset(data.id) }) }
  async function loadDataset(id = datasetId) { const { data } = await evaluationApi.dataset(id); setDataset(data); setDatasetId(data.id); setEvaluationRequest(data.evaluation_request || null) }
  async function requestEvaluation() { await action(async () => { const { data } = await evaluationApi.requestRun(datasetId, { top_n: topN }); setEvaluationRequest(data); toast.success('Evaluation request sent to the admin queue.'); await loadDataset() }) }
  if (user?.role === 'admin') return <AdminEvaluationRunner />
  return <div className="page-wrap"><PageHeader eyebrow="QUALITY · EVALUATION" title="Measure relevance with labels" description="Label relevance and expected skill states, then review ranking, skill-gap, and evidence-grounding metrics." />{error && <ErrorState error={error} retry={() => datasetId && loadDataset()} />}
    {!datasetId ? <Card className="eval-create"><div className="composer-badge"><ActivityIcon /></div><div><h2>Create an evaluation set</h2><p>Create a labeled benchmark. Once it has human relevance labels, submit it to an administrator for a measured run.</p></div><form onSubmit={createDataset}><Field label="Dataset name" placeholder="e.g. Platform engineering benchmark" value={name} onChange={(e) => setName(e.target.value)} required /><Field label="Description (optional)" placeholder="What does this dataset evaluate?" value={description} onChange={(e) => setDescription(e.target.value)} /><Button loading={busy}><Plus size={15} /> Create dataset</Button></form></Card> : <div className="evaluation-layout"><Card className="evaluation-workbench"><div className="card-topline"><div><span className="eyebrow">LABELING WORKBENCH</span><h2>{dataset?.name || 'Evaluation dataset'}</h2></div><Button variant="quiet" onClick={() => loadDataset()}><RefreshCw size={14} /> Refresh</Button></div><label className="field"><span>Dataset ID</span><input value={datasetId} onChange={(e) => setDatasetId(e.target.value)} onBlur={() => loadDataset()} /></label><form className="query-form" onSubmit={(e) => { e.preventDefault(); action(async () => { await evaluationApi.addQuery(datasetId, { query_text: query }); setQuery(''); toast.success('Evaluation query added.'); await loadDataset() }) }}><TextArea label="Add evaluation query" placeholder="Enter a representative hiring requirement…" value={query} onChange={(e) => setQuery(e.target.value)} rows={3} required /><Button loading={busy}><Plus size={14} /> Add query</Button></form>{dataset?.queries?.length ? dataset.queries.map((q) => <div className="eval-query" key={q.id}><div><strong>{q.query_text}</strong><small>{q.labels?.length || 0} relevance labels</small></div><form onSubmit={(e) => { e.preventDefault(); action(async () => { const statuses = JSON.parse(skillStatuses || '{}'); if (!statuses || Array.isArray(statuses) || typeof statuses !== 'object') throw new Error('Skill labels must be a JSON object.'); await evaluationApi.label(q.id, { candidate_id: candidateId, relevance: Number(relevance), skill_statuses: statuses }); setCandidateId(''); setSkillStatuses('{}'); toast.success('Candidate labels saved.'); await loadDataset() }) }}><input aria-label="Candidate ID to label" placeholder="Candidate ID" value={candidateId} onChange={(e) => setCandidateId(e.target.value)} required /><input aria-label="Expected skill statuses as JSON" placeholder="Skill labels JSON (optional), e.g. {&quot;Python&quot;:&quot;matched&quot;}" value={skillStatuses} onChange={(e) => setSkillStatuses(e.target.value)} /><select aria-label="Relevance" value={relevance} onChange={(e) => setRelevance(e.target.value)}><option value="0">0 · Not relevant</option><option value="1">1 · Relevant</option><option value="2">2 · Highly relevant</option></select><Button variant="secondary" loading={busy}>Add label</Button></form>{q.labels?.length > 0 && <div className="label-tags">{q.labels.map((l) => <Badge key={l.candidate_id}>Candidate {l.candidate_id.slice(0, 7)} · {l.relevance}{Object.keys(l.skill_statuses || {}).length ? ` ? ${Object.keys(l.skill_statuses).length} skill labels` : ''}</Badge>)}</div>}</div>) : <EmptyState title="Add your first query" text="Each query needs one or more human relevance labels before the run is meaningful." />}</Card><Card className="eval-run-card"><span className="eyebrow">ADMIN REVIEW</span><h2>Request evaluation</h2><p>Send this labeled dataset to the admin queue. Admins can run the metrics without manually re-entering your dataset ID.</p><label className="field"><span>Results at K</span><select value={topN} onChange={(e) => setTopN(Number(e.target.value))}><option value="3">3</option><option value="5">5</option><option value="10">10</option></select></label>{(!evaluationRequest || evaluationRequest.status === 'completed' || evaluationRequest.status === 'failed') ? <Button loading={busy} disabled={!dataset?.queries?.some((q) => q.labels?.length)} onClick={requestEvaluation}>{evaluationRequest?.status === 'completed' ? 'Request another evaluation' : evaluationRequest?.status === 'failed' ? 'Resubmit evaluation request' : 'Send to admin for evaluation'}</Button> : <Badge tone={evaluationRequest.status === 'running' ? 'amber' : 'mint'}>Request {evaluationRequest.status}</Badge>}{!dataset?.queries?.some((q) => q.labels?.length) && <small className="field-hint">Add at least one human relevance label before sending.</small>}{evaluationRequest && <p className="muted">Request status: {evaluationRequest.status}. The admin will run the evaluation from their request queue.</p>}{evaluationRequest?.status === 'completed' && evaluationRequest.metrics && <div className="metrics-result"><div className="eyebrow">ADMIN RUN RESULTS</div><MetricsGrid metrics={evaluationRequest.metrics} />{evaluationRequest.notes && <p className="muted">{evaluationRequest.notes}</p>}</div>}<div className="inline-note"><ShieldCheck size={15} /> Metrics are computed from the saved human labels; unlabeled queries are skipped.</div></Card></div>}
  </div>
}
function MetricsGrid({ metrics }) {
  const sections = [
    { id: 'ranking', title: 'Retrieval & ranking', keys: /precision|recall|mrr|ndcg|queries_evaluated|ranked|retrieved/i },
    { id: 'matching', title: 'Requirement matching', keys: /skill_gap|matching|requirement|macro_f1/i },
    { id: 'evidence', title: 'Evidence quality', keys: /evidence|grounding|claim|validation|flagged/i },
  ]
  const flat = Object.entries(metrics || {}).flatMap(([key, value]) => value && typeof value === 'object' && !Array.isArray(value)
    ? Object.entries(value).flatMap(([group, scores]) => scores && typeof scores === 'object'
      ? Object.entries(scores).map(([metric, score]) => ({ key: `${key}-${group}-${metric}`, name: `${group} ${metric}`, value: score, detail: `${group} · ${metric}` }))
      : [{ key: `${key}-${group}`, name: group, value: scores, detail: key.replaceAll('_', ' ') }])
    : [{ key, name: key.replaceAll('_', ' '), value, detail: key.replaceAll('_', ' ') }])
  const used = new Set()
  const groups = sections.map((section) => ({ ...section, items: flat.filter((item) => { const match = section.keys.test(`${item.key} ${item.name}`); if (match) used.add(item.key); return match }) })).filter((section) => section.items.length)
  const other = flat.filter((item) => !used.has(item.key))
  if (other.length) groups.push({ id: 'other', title: 'Run coverage & additional metrics', items: other })
  return <div className="evaluation-dashboard">{groups.map((section) => <section className="evaluation-metric-section" key={section.id}><div className="eyebrow">{section.title}</div><div className="metric-grid small-metrics">{section.items.map((item) => {
    const numeric = typeof item.value === 'number' && Number.isFinite(item.value), ratio = numeric && item.value >= 0 && item.value <= 1 && !/queries|items|candidates|claims|labels|count/i.test(item.key)
    const display = numeric ? (ratio ? `${(item.value * 100).toFixed(1)}%` : Number.isInteger(item.value) ? item.value.toLocaleString() : item.value.toFixed(3)) : item.value ?? 'N/A'
    return <div className="evaluation-metric" key={item.key}><strong>{display}</strong><span>{item.detail}</span>{ratio && <i><b style={{ width: `${Math.max(0, Math.min(100, item.value * 100))}%` }} /></i>}</div>
  })}</div></section>)}</div>
}

function ActivityIcon() { return <Clock3 size={18} /> }

function AdminEvaluationRunner() {
  const [requests, setRequests] = useState(null), [result, setResult] = useState(null), [error, setError] = useState(''), [busyId, setBusyId] = useState('')
  async function loadRequests() { try { const { data } = await evaluationApi.requests(); setRequests(data) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { loadRequests() }, [])
  async function runRequest(request) { setBusyId(request.id); setError(''); setResult(null); try { const { data } = await evaluationApi.runRequest(request.id); setResult(data.result); toast.success('Evaluation run completed.'); await loadRequests() } catch (e) { setError(errorMessage(e)); await loadRequests() } finally { setBusyId('') } }
  return <div className="page-wrap"><PageHeader eyebrow="QUALITY · ADMIN EVALUATION" title="HR evaluation requests" description="Run metrics on labeled datasets submitted by HR. Candidate labels remain private; this queue exposes only the dataset and requester details." action={<Button variant="secondary" onClick={loadRequests}><RefreshCw size={15} /> Refresh requests</Button>} />{error && <ErrorState error={error} retry={loadRequests} />}<Card className="eval-request-queue"><div className="card-topline"><div><span className="eyebrow">SUBMITTED BY HR</span><h2>Evaluation queue</h2></div></div>{!requests && !error ? <LoadingState /> : requests?.length ? <div className="eval-request-list">{requests.map((request) => <article className="eval-request-row" key={request.id}><div className="eval-request-copy"><div><strong>{request.dataset_name}</strong><Badge tone={request.status === 'completed' ? 'mint' : request.status === 'failed' ? 'rose' : request.status === 'pending' ? 'amber' : 'neutral'}>{request.status}</Badge></div><span>Requested by {request.requested_by_name} · {request.requested_by_email}</span><small>Requested Results at K: {request.top_n} · Dataset ID: <code>{request.dataset_id}</code> · {new Date(request.created_at).toLocaleString()}</small></div>{request.status === 'pending' && <Button loading={busyId === request.id} disabled={Boolean(busyId)} onClick={() => runRequest(request)}><ActivityIcon /> Run evaluation</Button>}</article>)}</div> : <EmptyState title="No HR requests yet" text="When an HR user submits a labeled dataset, it will appear here with a one-click evaluation action." />}</Card>{result && <Card className="admin-eval-result"><div className="card-topline"><div><span className="eyebrow">BACKEND RESULT</span><h2>Evaluation metrics</h2></div><Badge>Top {result.top_n}</Badge></div><MetricsGrid metrics={result.metrics || {}} />{result.notes && <p className="muted">{result.notes}</p>}</Card>}</div>
}

function Notifications() {
  const [rows, setRows] = useState(null), [error, setError] = useState('')
  async function load() { try { const { data } = await notificationApi.list(); setRows(data) } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  async function mark(ids) { try { await notificationApi.markRead(ids); toast.success('Notifications marked as read.'); await load(); window.dispatchEvent(new Event('ri:notifications-changed')) } catch (e) { setError(errorMessage(e)) } }
  return <div className="page-wrap"><PageHeader eyebrow="INBOX · NOTIFICATIONS" title="Notifications" description="Stay current on resume processing and activity from your workspace." action={rows?.some((x) => !x.is_read) && <Button variant="secondary" onClick={() => mark(null)}><Check size={15} /> Mark all read</Button>} />{error && <ErrorState error={error} retry={load} />}{!rows && !error ? <LoadingState /> : rows?.length ? <Card className="notification-list">{rows.map((n) => <article className={`notification-row ${n.is_read ? '' : 'unread'}`} key={n.id}><div className="notification-icon"><Bell size={16} /></div><div className="notification-copy"><div><strong>{n.title}</strong><span className="notification-time">{new Date(n.created_at).toLocaleString()}</span></div><p>{n.message}</p><Badge>{n.notification_type.replaceAll('_', ' ')}</Badge></div>{!n.is_read && <button className="mark-read" onClick={() => mark([n.id])} aria-label="Mark notification read"><Check size={16} /></button>}</article>)}</Card> : <EmptyState title="You’re all caught up" text="New notifications will appear here." />}</div>
}

function Profile() {
  const [profile, setProfile] = useState(null), [name, setName] = useState(''), [phone, setPhone] = useState(''), [currentPassword, setCurrent] = useState(''), [newPassword, setNew] = useState(''), [notice, setNotice] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  async function load() { try { const { data } = await profileApi.get(); setProfile(data); setName(data.full_name); setPhone(data.phone || '') } catch (e) { setError(errorMessage(e)) } }
  useEffect(() => { load() }, [])
  async function save(e) { e.preventDefault(); setBusy(true); setNotice(''); setError(''); try { const { data } = await profileApi.update({ full_name: name, phone: phone || null }); setProfile(data); setNotice('Profile updated.') } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  async function password(e) { e.preventDefault(); setBusy(true); setError(''); setNotice(''); try { await (await import('../api/endpoints')).authApi.changePassword({ current_password: currentPassword, new_password: newPassword }); setCurrent(''); setNew(''); setNotice('Password changed successfully.') } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }
  return <div className="page-wrap"><PageHeader eyebrow="YOUR ACCOUNT · PROFILE & SETTINGS" title="Profile & security" description="Manage your account information and sign-in security." />{error && <ErrorState error={error} retry={load} />}{notice && <div className="success-banner"><Check size={15} />{notice}</div>}{!profile && !error ? <LoadingState /> : profile && <div className="profile-grid"><Card className="profile-card"><div className="profile-hero"><div className="profile-avatar">{profile.full_name.slice(0, 1).toUpperCase()}</div><div><span className="eyebrow">{profile.role.toUpperCase()} ACCOUNT</span><h2>{profile.full_name}</h2><span>{profile.email}</span></div><Badge tone={profile.is_active ? 'mint' : 'rose'}>{profile.is_active ? 'Active' : 'Disabled'}</Badge></div><form onSubmit={save}><Field label="Full name" value={name} onChange={(e) => setName(e.target.value)} required /><Field label="Email address" value={profile.email} disabled /><Field label="Phone" placeholder="Add a phone number" value={phone} onChange={(e) => setPhone(e.target.value)} /><Button loading={busy}><Save size={15} /> Save profile</Button></form><div className="profile-meta"><span>Member since {new Date(profile.created_at).toLocaleDateString()}</span><span>Last sign-in {profile.last_login_at ? new Date(profile.last_login_at).toLocaleString() : 'Not recorded'}</span></div></Card><Card className="security-card"><span className="security-icon"><ShieldCheck size={18} /></span><span className="eyebrow">SECURITY</span><h2>Change password</h2><p>Use at least 8 characters for your new password.</p><form onSubmit={password}><Field label="Current password" type="password" value={currentPassword} onChange={(e) => setCurrent(e.target.value)} required /><Field label="New password" type="password" minLength={8} value={newPassword} onChange={(e) => setNew(e.target.value)} required /><Button variant="secondary" loading={busy}>Update password</Button></form><div className="inline-note"><ShieldCheck size={15} /> Sessions refresh automatically when the service accepts the refresh token.</div></Card></div>}</div>
}
