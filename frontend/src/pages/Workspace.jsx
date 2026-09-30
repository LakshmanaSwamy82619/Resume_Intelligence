import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ArrowRight, BriefcaseBusiness, Clock3, FileText, Search, Sparkles, UsersRound } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { hrApi, candidateApi } from '../api/endpoints'
import { errorMessage } from '../api/client'
import { Badge, Card, EmptyState, ErrorState, LoadingState, MetricCard, PageHeader } from '../components/UI'

export default function Workspace() {
  const [searches, setSearches] = useState(null)
  const [searchActivity, setSearchActivity] = useState([])
  const [summary, setSummary] = useState(null)
  const [candidateCount, setCandidateCount] = useState(null)
  const [resumeCount, setResumeCount] = useState(null)
  const [error, setError] = useState('')
  async function load() {
    setError('')
    try {
      const [s, c] = await Promise.all([hrApi.overview(), candidateApi.list(1, 1)])
      setSummary(s.data); setSearches(s.data.recent_searches || []); setSearchActivity(s.data.search_activity || []); setCandidateCount(c.data.total); setResumeCount(c.data.total_resumes)
    } catch (e) { setError(errorMessage(e)) }
  }
  useEffect(() => { load() }, [])
  const chart = useMemo(() => {
    const grouped = new Map()
    searchActivity.forEach((createdAt) => { const d = new Date(createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); grouped.set(d, (grouped.get(d) || 0) + 1) })
    return [...grouped.entries()].map(([date, searches]) => ({ date, searches }))
  }, [searchActivity])
  if (!searches && !error) return <LoadingState />
  return <div className="page-wrap hr-dashboard">
    <PageHeader eyebrow="RECRUITER WORKSPACE · OVERVIEW" title="Find the right candidate faster." description="Search resume profiles with semantic matching, then inspect the evidence behind every recommendation." action={<Link className="button button-primary" to="/search"><Sparkles size={16} /> Search candidates</Link>} />
    {error && <ErrorState error={error} retry={load} />}
    {searches && <>
      <section className="workspace-section" aria-labelledby="workspace-pulse-title"><div className="section-heading"><div><span className="eyebrow">YOUR TALENT PIPELINE</span><h2 id="workspace-pulse-title">Workspace pulse</h2></div><span>Based on your recent searches and indexed talent</span></div><div className="metric-grid workspace-metrics">
        <MetricCard label="Resumes indexed" value={resumeCount} icon={UsersRound} detail={`${candidateCount ?? 0} unique candidate profiles`} />
        <MetricCard label="Total searches" value={summary?.total_searches ?? 0} icon={Search} detail="All saved searches in your workspace" />
        <MetricCard label="Latest result pool" value={summary?.latest_result_pool ?? '—'} icon={Activity} detail={summary?.latest_result_pool != null ? 'Candidates retrieved in last search' : 'No searches recorded'} />
        <MetricCard label="Avg. search time" value={summary?.average_search_time_ms == null ? '—' : `${Math.round(summary.average_search_time_ms)} ms`} icon={Clock3} detail="Across all saved searches with timing" />
      </div></section>
      <section className="workspace-section" aria-labelledby="search-activity-title"><div className="section-heading"><div><span className="eyebrow">RECRUITER WORKFLOW</span><h2 id="search-activity-title">Search activity and next steps</h2></div></div><div className="dashboard-grid">
        <Card className="chart-card"><div className="card-topline"><div><span className="eyebrow">YOUR ACTIVITY</span><h2>Search momentum</h2></div><Badge tone="mint">All searches · daily</Badge></div>{chart.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chart} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}><defs><linearGradient id="activityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8caeff" stopOpacity={.25} /><stop offset="100%" stopColor="#8caeff" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#303a50" vertical={false} /><XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: '#929eb4', fontSize: 11 }} /><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: '#929eb4', fontSize: 11 }} /><Tooltip contentStyle={{ background: '#171e2e', border: '1px solid #394662', borderRadius: 12, color: '#edf2fb' }} /><Area type="monotone" dataKey="searches" stroke="#9eb9ff" strokeWidth={2.5} fill="url(#activityFill)" /></AreaChart></ResponsiveContainer></div> : <EmptyState title="Your first search is waiting" text="Search activity will appear here when you run a candidate search." action={<Link to="/search" className="button button-quiet">Explore candidate intelligence <ArrowRight size={15} /></Link>} />}</Card>
        <Card className="pipeline-card"><div className="card-topline"><div><span className="eyebrow">QUICK ACCESS</span><h2>Talent workspace</h2></div><span className="spark-icon"><Sparkles size={17} /></span></div><Link className="quick-row" to="/resumes"><span className="quick-icon"><FileText size={17} /></span><span><strong>Resume library</strong><small>Upload and review indexed candidates</small></span><ArrowRight size={16} /></Link><Link className="quick-row" to="/jobs"><span className="quick-icon purple"><BriefcaseBusiness size={17} /></span><span><strong>Job briefs</strong><small>Structure a role before matching</small></span><ArrowRight size={16} /></Link><Link className="quick-row" to="/history"><span className="quick-icon amber"><Clock3 size={17} /></span><span><strong>Search history</strong><small>Return to a previous shortlist</small></span><ArrowRight size={16} /></Link><div className="privacy-foot"><span className="tiny-lock">✦</span> Every match is anchored to resume evidence</div></Card>
      </div>
      </section><Card className="recent-card"><div className="card-topline"><div><span className="eyebrow">RECRUITER ACTIVITY · LATEST</span><h2>Recent searches</h2></div><Link className="text-link" to="/history">View history <ArrowRight size={15} /></Link></div>{searches.length ? <div className="table-scroll"><table><thead><tr><th>Hiring requirement</th><th>Top N</th><th>Pool</th><th>Latency</th><th>Provider path</th><th></th></tr></thead><tbody>{searches.slice(0, 5).map((s) => <tr key={s.id}><td><span className="row-title">{s.query_text}</span><small className="row-sub">{new Date(s.created_at).toLocaleString()}</small></td><td><Badge>Top {s.top_n_requested}</Badge></td><td>{s.candidate_pool_size}</td><td>{s.processing_time_ms == null ? '—' : `${Math.round(s.processing_time_ms)} ms`}</td><td><Badge tone={s.fallback_used ? 'amber' : 'mint'}>{s.fallback_used ? 'Fallback used' : 'Standard'}</Badge></td><td><Link className="table-action" to={`/history?search=${s.id}`} aria-label="Open search"><ArrowRight size={16} /></Link></td></tr>)}</tbody></table></div> : <EmptyState title="No searches yet" text="Your searches and candidate shortlists will show up here." action={<Link to="/search" className="button button-primary">Run your first search <ArrowRight size={15} /></Link>} />}</Card>
    </>}
  </div>
}
