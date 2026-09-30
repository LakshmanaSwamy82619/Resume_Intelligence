import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, Bell, BriefcaseBusiness, Command, FileText, GitCompareArrows, LayoutDashboard, LogOut, Menu, Search, Settings2, Shield, UsersRound, X, PanelLeftClose, PanelLeftOpen, Workflow, BookmarkCheck } from 'lucide-react'
import { useAuth } from '../state/AuthContext'
import { notificationApi } from '../api/endpoints'
import { Button } from '../components/UI'
import ThemeToggle from '../components/ThemeToggle'

const hrLinks = [
  ['Overview', '/workspace', LayoutDashboard], ['Find talent', '/search', Search], ['Resume library', '/resumes', FileText], ['Job briefs', '/jobs', BriefcaseBusiness], ['Compare', '/compare', GitCompareArrows], ['Shortlists', '/shortlists', BookmarkCheck], ['Search history', '/history', Activity], ['Evaluation', '/evaluation', Command], ['Notifications', '/notifications', Bell], ['Profile & settings', '/profile', Settings2],
]
const adminLinks = [['Overview', '/admin', LayoutDashboard], ['Query pipeline', '/admin/pipeline', Workflow], ['HR accounts', '/admin/hr', UsersRound], ['System analytics', '/admin/analytics', Activity], ['Evaluation', '/evaluation', Command], ['Audit logs', '/admin/audit', Shield], ['System health', '/admin/health', Bell], ['Notifications', '/notifications', Bell], ['Profile & settings', '/profile', Settings2]]

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('ri_sidebar_collapsed') === 'true')
  const [unreadCount, setUnreadCount] = useState(0)
  const isAdmin = user?.role === 'admin'
  const links = isAdmin ? adminLinks : hrLinks
  function leave() { logout(); navigate('/login') }
  useEffect(() => { const refresh = () => notificationApi.list(true).then(({ data }) => setUnreadCount(data.length)).catch(() => {}); refresh(); window.addEventListener('ri:notifications-changed', refresh); return () => window.removeEventListener('ri:notifications-changed', refresh) }, [])
  function toggleSidebar() { setCollapsed((value) => { localStorage.setItem('ri_sidebar_collapsed', String(!value)); return !value }) }
  return <div className={`app-shell ${collapsed ? 'sidebar-closed' : ''}`}>
    <AnimatePresence>{open && <motion.button className="mobile-scrim" onClick={() => setOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} aria-label="Close navigation" />}</AnimatePresence>
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`} aria-hidden={collapsed && !open}>
      <div className="brand"><div className="brand-mark"><span /><span /><span /></div><div className="brand-copy"><b>Resume<span> Intelligence</span></b><small>HIRING WORKSPACE</small></div><button className="mobile-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-switch"><span className="workspace-dot">{isAdmin ? 'A' : 'R'}</span><div><strong>{isAdmin ? 'System console' : 'Your workspace'}</strong><small>{isAdmin ? 'Administrator' : 'Recruiting workspace'}</small></div></div>
      <div className="sidebar-navigation"><div className="nav-label">WORKSPACE</div>
      <nav className="nav-list">{links.map(([label, to, Icon]) => <NavLink key={to} title={collapsed ? label : undefined} aria-label={collapsed ? label : undefined} to={to} end={to === '/workspace' || to === '/admin'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{label === 'Notifications' && unreadCount > 0 && <span className="unread-count">{unreadCount > 9 ? '9+' : unreadCount}</span>}</NavLink>)}</nav></div>
      <div className="user-menu"><div className="avatar">{user?.full_name?.slice(0, 1)?.toUpperCase() || 'U'}</div><div className="user-copy"><strong>{user?.full_name || 'Workspace user'}</strong><span>{user?.email}</span></div><button className="icon-button" aria-label="Sign out" onClick={leave}><LogOut size={16} /></button></div>
    </aside>
    <main className="main-column"><div className="topbar"><button className="mobile-menu icon-button" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><button className="sidebar-toggle icon-button" onClick={toggleSidebar} aria-label={collapsed ? 'Open navigation' : 'Close navigation'} title={collapsed ? 'Open navigation' : 'Close navigation'}>{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button><div className="breadcrumb"><span>Resume Intelligence</span><span className="crumb-slash">/</span><strong>{links.find((x) => x[1] === location.pathname)?.[0] || 'Workspace'}</strong></div><div className="topbar-right"><span className="workspace-label">{isAdmin ? 'System console' : 'Recruiting workspace'}</span><ThemeToggle /><LiveClock /><button className="topbar-avatar" title={user?.email}>{user?.full_name?.slice(0, 1)?.toUpperCase()}</button></div></div><AnimatePresence mode="wait"><motion.div key={location.pathname} className="main-content" initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }} animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} exit={{ opacity: 0 }} transition={{ duration: .35, ease: [.16, 1, .3, 1] }}><Outlet /></motion.div></AnimatePresence></main>
  </div>
}

function LiveClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const timeParts = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h12' }).formatToParts(now)
  const value = timeParts.map((part) => part.type === 'dayPeriod' ? part.value.toUpperCase() : part.value).join('')
  return <time className="topbar-clock" dateTime={now.toISOString()} aria-label={`Current local time ${value}`}>{value}</time>
}
