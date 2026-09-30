import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { MotionConfig } from 'framer-motion'
import AppLayout from './layouts/AppLayout'
import { useAuth } from './state/AuthContext'
import { LoadingState } from './components/UI'
import ToastViewport from './components/ToastViewport'
import AuthPage from './pages/AuthPage'
import FirstLoginPasswordPage from './pages/FirstLoginPasswordPage'

const Workspace = lazy(() => import('./pages/Workspace'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const DataPages = lazy(() => import('./pages/DataPages'))
const AdminPages = lazy(() => import('./pages/AdminPages'))

export function RequireAuth({ children, role }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <LoadingState />
  if (!user) return <Navigate to="/login" replace />
  if (user.must_change_password && location.pathname !== '/first-login-password') return <Navigate to="/first-login-password" replace />
  if (role === 'admin' && user.role !== 'admin') return <Navigate to="/workspace" replace />
  if (role === 'hr' && user.role !== 'hr') return <Navigate to="/admin" replace />
  return children
}
function Protected({ role, children }) { return <RequireAuth role={role}><AppLayout /></RequireAuth> }
function FirstLoginPasswordRoute() {
  const { user, loading } = useAuth()
  if (loading) return <LoadingState />
  if (!user) return <Navigate to="/login" replace />
  if (!user.must_change_password) return <Navigate to={user.role === 'admin' ? '/admin' : '/workspace'} replace />
  return <FirstLoginPasswordPage />
}

export default function App() {
  const { user } = useAuth()
  return <MotionConfig reducedMotion="user"><ToastViewport /><Suspense fallback={<LoadingState />}><Routes>
    <Route path="/login" element={user ? <Navigate to={user.must_change_password ? '/first-login-password' : user.role === 'admin' ? '/admin' : '/workspace'} replace /> : <AuthPage />} />
    <Route path="/first-login-password" element={<FirstLoginPasswordRoute />} />
    <Route path="/forgot-password" element={<AuthPage mode="forgot" />} />
    <Route path="/verify-otp" element={<AuthPage mode="verify" />} />
    <Route path="/reset-password" element={<AuthPage mode="reset" />} />
    <Route element={<Protected role="hr" />}>
      <Route path="/workspace" element={<Workspace />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/resumes" element={<DataPages page="resumes" />} />
      <Route path="/jobs" element={<DataPages page="jobs" />} />
      <Route path="/compare" element={<DataPages page="compare" />} />
      <Route path="/shortlists" element={<DataPages page="shortlists" />} />
      <Route path="/history" element={<DataPages page="history" />} />
    </Route>
    <Route element={<Protected role="admin" />}>
      <Route path="/admin" element={<AdminPages page="overview" />} />
      <Route path="/admin/hr" element={<AdminPages page="hr" />} />
      <Route path="/admin/analytics" element={<AdminPages page="analytics" />} />
      <Route path="/admin/pipeline" element={<AdminPages page="pipeline" />} />
      <Route path="/admin/audit" element={<AdminPages page="audit" />} />
      <Route path="/admin/health" element={<AdminPages page="health" />} />
    </Route>
    <Route element={<Protected />}>
      <Route path="/profile" element={<DataPages page="profile" />} />
      <Route path="/evaluation" element={<DataPages page="evaluation" />} />
      <Route path="/notifications" element={<DataPages page="notifications" />} />
    </Route>
    <Route path="*" element={<Navigate to={user ? (user.must_change_password ? '/first-login-password' : user.role === 'admin' ? '/admin' : '/workspace') : '/login'} replace />} />
  </Routes></Suspense></MotionConfig>
}
