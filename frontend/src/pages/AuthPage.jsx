import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, KeyRound, Mail, ShieldCheck, Sparkles } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { authApi } from '../api/endpoints'
import { errorMessage } from '../api/client'
import { useAuth } from '../state/AuthContext'
import { Button, Field } from '../components/UI'
import ResumeScan from '../components/ResumeScan'
import ThemeToggle from '../components/ThemeToggle'

const content = {
  login: ['A sharper lens on every candidate.', 'Evidence-led matching for the people who build great teams.'],
  forgot: ['Let’s get you back in.', 'We’ll send a one-time verification code to your account email.'],
  verify: ['One quick security check.', 'Enter the verification code sent to your email address.'],
  reset: ['Set a new password.', 'Choose a strong password you haven’t used before.'],
}
export default function AuthPage({ mode = 'login' }) {
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [otp, setOtp] = useState(''), [newPassword, setNewPassword] = useState(''), [showPassword, setShowPassword] = useState(false), [loading, setLoading] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState('')
  const { signIn } = useAuth(), navigate = useNavigate(), location = useLocation()
  const resetToken = location.state?.resetToken
  const activeMode = mode === 'reset' && resetToken ? 'reset' : mode
  async function submit(e) {
    e.preventDefault(); setLoading(true); setError(''); setSuccess('')
    try {
      if (activeMode === 'login') { const user = await signIn(email, password); navigate(user.must_change_password ? '/first-login-password' : user.role === 'admin' ? '/admin' : '/workspace', { replace: true }) }
      if (activeMode === 'forgot') {
        const { data } = await authApi.forgot(email)
        if (!data?.account_exists) { setError(data?.message || 'This email is not associated with an account in your organization.'); return }
        if (!data.otp_sent) { setError(data.message || 'This account cannot receive a verification code. Contact your administrator.'); return }
        setSuccess(data.message || 'A verification code has been sent to your email address.')
        sessionStorage.setItem('ri_reset_email', email)
        setTimeout(() => navigate('/verify-otp'), 650)
      }
      if (activeMode === 'verify') { const target = email || sessionStorage.getItem('ri_reset_email') || ''; const { data } = await authApi.verifyOtp({ email: target, otp_code: otp }); navigate('/reset-password', { state: { resetToken: data.reset_token, email: target } }) }
      if (activeMode === 'reset') { const target = location.state?.email || sessionStorage.getItem('ri_reset_email') || email; await authApi.reset({ email: target, reset_token: resetToken, new_password: newPassword }); sessionStorage.removeItem('ri_reset_email'); setSuccess('Your password has been reset. You can sign in now.'); setTimeout(() => navigate('/login'), 900) }
    } catch (err) { setError(activeMode === 'login' && err.response?.status === 401 ? 'Email or password is incorrect.' : activeMode === 'login' && err.response?.status === 403 && typeof err.response?.data?.detail === 'string' ? err.response.data.detail : errorMessage(err)) } finally { setLoading(false) }
  }
  const [title, subtitle] = content[activeMode]
  return <main className="auth-shell"><ThemeToggle className="auth-theme-toggle" /><section className="auth-aside"><Link to="/login" className="auth-brand"><div className="brand-mark"><span /><span /><span /></div><b>Resume<span> Intelligence</span></b></Link><ResumeScan /><div className="auth-aside-copy"><span className="eyebrow">THE SIGNAL, IN CONTEXT</span><h2>Recruiting decisions,<br />with the evidence attached.</h2><p>Search across resume intelligence. See what aligns, what doesn’t, and exactly where it came from.</p></div><div className="auth-legal"><span>© {new Date().getFullYear()} Resume Intelligence</span><span><ShieldCheck size={13} /> Secure workspace</span></div></section><section className="auth-main"><div className="auth-mobile-brand"><div className="brand-mark"><span /><span /><span /></div><b>Resume<span> Intelligence</span></b></div><div className="auth-form-wrap"><AnimatePresence mode="wait"><motion.div key={activeMode} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: .22 }}><div className="auth-form-head"><span className="eyebrow">{activeMode === 'login' ? 'RECRUITER & ADMIN ACCESS' : 'ACCOUNT RECOVERY'}</span><h1>{title}</h1><p>{subtitle}</p></div>{error && <div className="auth-error" role="alert">{error}</div>}{success && <div className="auth-success" role="status"><Check size={16} />{success}</div>}<form className="auth-form" onSubmit={submit}>
    {(activeMode === 'login' || activeMode === 'forgot' || activeMode === 'verify') && <Field label="Work email" type="email" autoComplete="email" placeholder="you@company.com" value={email || (activeMode !== 'login' ? location.state?.email || sessionStorage.getItem('ri_reset_email') || '' : '')} onChange={(e) => setEmail(e.target.value)} required />}
    {activeMode === 'login' && <label className="field"><span>Password <Link to="/forgot-password">Forgot password?</Link></span><div className="password-input"><input type={showPassword ? 'text' : 'password'} autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)} required /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div></label>}
    {activeMode === 'verify' && <Field label="One-time code" inputMode="numeric" autoComplete="one-time-code" placeholder="Enter verification code" maxLength={12} value={otp} onChange={(e) => setOtp(e.target.value)} required />}
    {activeMode === 'reset' && <label className="field"><span>New password</span><div className="password-input"><input type={showPassword ? 'text' : 'password'} autoComplete="new-password" minLength={8} placeholder="At least 8 characters" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div><small>Use at least 8 characters.</small></label>}
    <Button className="auth-submit" loading={loading}>{activeMode === 'login' ? 'Sign in to workspace' : activeMode === 'forgot' ? 'Send verification code' : activeMode === 'verify' ? 'Verify code' : 'Reset password'} <ArrowRight size={16} /></Button>
  </form><div className="auth-bottom">{activeMode === 'login' ? <span>Access is managed by your workspace administrator.</span> : <Link to={activeMode === 'verify' || activeMode === 'reset' ? '/forgot-password' : '/login'}><ArrowLeft size={14} /> {activeMode === 'verify' || activeMode === 'reset' ? 'Start over' : 'Back to sign in'}</Link>}</div></motion.div></AnimatePresence></div><div className="auth-main-foot"><span>Private by design</span><span>·</span><span>Your organization controls access</span></div></section></main>
}
