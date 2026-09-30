import { useState } from 'react'
import { Check, Circle, CircleCheck, Eye, EyeOff, KeyRound, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/UI'
import { errorMessage } from '../api/client'
import { useAuth } from '../state/AuthContext'
import ThemeToggle from '../components/ThemeToggle'

const requirements = [
  ['At least 8 characters', (value) => value.length >= 8],
  ['At least one uppercase letter', (value) => /[A-Z]/.test(value)],
  ['At least one lowercase letter', (value) => /[a-z]/.test(value)],
  ['At least one number', (value) => /[0-9]/.test(value)],
  ['At least one special character', (value) => /[^A-Za-z0-9\s]/.test(value)],
]

export default function FirstLoginPasswordPage() {
  const { user, completeFirstLogin, logout } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const allRequirementsMet = requirements.every(([, check]) => check(password))

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (!allRequirementsMet) return setError('Meet every password requirement to continue.')
    if (password !== confirmation) return setError('The passwords do not match.')
    setBusy(true)
    try {
      const updatedUser = await completeFirstLogin(password)
      navigate(updatedUser.role === 'admin' ? '/admin' : '/workspace', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return <main className="first-login-shell">
    <ThemeToggle className="first-login-theme-toggle" />
    <section className="first-login-card">
      <div className="first-login-icon"><KeyRound size={22} /></div>
      <span className="eyebrow">FIRST SIGN-IN SECURITY</span>
      <h1>Set your new password</h1>
      <p className="first-login-description">Welcome{user?.full_name ? `, ${user.full_name}` : ''}. Replace your temporary password to continue to your HR workspace.</p>
      {error && <div className="auth-error" role="alert">{error}</div>}
      <form className="auth-form" onSubmit={submit}>
        <label className="field">
          <span>New password</span>
          <div className="password-input">
            <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required />
            <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>
          </div>
        </label>
        <ul className="password-rules" aria-label="Password requirements">
          {requirements.map(([label, check]) => {
            const met = check(password)
            return <li className={met ? 'met' : ''} key={label}>{met ? <CircleCheck size={16} /> : <Circle size={16} />}{label}</li>
          })}
        </ul>
        <label className="field">
          <span>Confirm new password</span>
          <input type={showPassword ? 'text' : 'password'} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" required />
          {confirmation && confirmation !== password && <small className="password-mismatch">Passwords do not match.</small>}
        </label>
        <Button className="auth-submit" loading={busy} disabled={!allRequirementsMet || !confirmation || confirmation !== password}><ShieldCheck size={16} /> Set password and continue</Button>
      </form>
      <button className="auth-text-button" type="button" onClick={() => { logout(); navigate('/login', { replace: true }) }}>Sign out</button>
    </section>
  </main>
}
