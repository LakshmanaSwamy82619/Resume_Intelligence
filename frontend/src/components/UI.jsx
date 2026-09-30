import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { AlertCircle, AlertTriangle, ArrowUpRight, Check, LoaderCircle, SearchX, X } from 'lucide-react'

export function Button({ children, className = '', variant = 'primary', loading = false, ...props }) {
  return <motion.button {...props} whileTap={{ scale: .985 }} whileHover={props.disabled || loading ? undefined : { y: -1 }} className={`button button-${variant} ${className}`} disabled={loading || props.disabled} aria-busy={loading || undefined}>{loading && <LoaderCircle size={16} className="spin" />}{children}</motion.button>
}
export function Card({ children, className = '', ...props }) { return <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .24 }} whileHover={{ y: -2 }} className={`card ${className}`} {...props}>{children}</motion.section> }
export function PageHeader({ eyebrow, title, description, action }) { return <header className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="header-action">{action}</div>}</header> }
export function LoadingState({ label = 'Loading your workspace…' }) { return <div className="state-box loading-state" role="status" aria-live="polite"><span className="loader-orb"><LoaderCircle className="spin" /></span><span>{label}</span><div className="state-skeleton" aria-hidden="true"><i /><i /><i /></div></div> }
export function Skeleton({ className = '' }) { return <span className={`skeleton ${className}`} aria-hidden="true" /> }
export function EmptyState({ title = 'Nothing here yet', text = 'When data is available, it will appear here.', action }) { return <div className="state-box empty"><span className="empty-icon"><SearchX /></span><strong>{title}</strong><span>{text}</span>{action}</div> }
export function ErrorState({ error, retry }) { return <div className="state-box error-state"><AlertCircle /><strong>{error || 'We couldn’t load this information.'}</strong>{retry && <Button variant="quiet" onClick={retry}>Try again <ArrowUpRight size={15} /></Button>}</div> }
const toneIcon = { mint: Check, amber: AlertTriangle, rose: X }
export function Badge({ children, tone = 'neutral', icon, iconOnly = false }) {
  const Icon = icon === null ? null : icon || toneIcon[tone]
  return <span className={`badge badge-${tone}`}>{Icon && <Icon size={11} className="badge-icon" aria-hidden="true" />}{!iconOnly && children}</span>
}
export function Progress({ value = 0 }) { return <div className="progress-track"><motion.div initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(100, value))}%` }} className="progress-fill" /></div> }
export function Modal({ title, children, onClose }) {
  const dialog = <div className="modal-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><motion.div initial={{ opacity: 0, y: 14, scale: .98 }} animate={{ opacity: 1, y: 0, scale: 1 }} className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-head"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}>×</button></div>{children}</motion.div></div>
  return createPortal(dialog, document.body)
}
export function Field({ label, hint, ...props }) { return <label className="field"><span>{label}</span><input {...props} />{hint && <small>{hint}</small>}</label> }
export function TextArea({ label, ...props }) { return <label className="field"><span>{label}</span><textarea {...props} /></label> }

// Circular match-score indicator. Never invents a value — pass the real backend score (0..1 or 0..100).
export function ScoreRing({ value, size = 56, label = 'match' }) {
  const pct = value == null ? null : Math.round((value > 1 ? value : value * 100))
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const offset = pct == null ? circumference : circumference * (1 - Math.max(0, Math.min(100, pct)) / 100)
  const tone = pct == null ? 'var(--muted)' : pct >= 75 ? 'var(--mint)' : pct >= 50 ? 'var(--amber)' : 'var(--rose)'
  return <div className="match-score-ring" style={{ width: size, height: size }} role="img" aria-label={pct == null ? `${label} score unavailable` : `${pct} percent ${label} score`}>
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--ring-track)" strokeWidth={4} />
      {pct != null && <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={tone} strokeWidth={4} strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset .6s cubic-bezier(.16,1,.3,1)' }} />}
    </svg>
    <div className="match-score-ring-value"><strong>{pct == null ? '—' : pct}</strong>{pct != null && <small>%</small>}</div>
  </div>
}
// Metric/stat card used on dashboards. Data-driven only — pass real values, never fabricated ones.
export function MetricCard({ label, value, icon: Icon, detail, tone = 'default' }) {
  return <Card className={`metric-card metric-card-${tone}`}>
    <div className="metric-head"><span>{label}</span>{Icon && <span className="metric-icon"><Icon size={17} /></span>}</div>
    <strong className="metric-value">{value == null || value === '' ? '—' : value}</strong>
    {detail && <div className="metric-detail">{detail}</div>}
  </Card>
}
export function GlassPanel({ children, className = '', ...props }) { return <div className={`glass-panel ${className}`} {...props}>{children}</div> }
