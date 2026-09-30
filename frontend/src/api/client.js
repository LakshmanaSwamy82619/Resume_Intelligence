import axios from 'axios'

// Uvicorn's local development server may bind only to IPv4. Using localhost
// can resolve to ::1 first in browsers and fail before reaching the API.
const configuredBaseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
// The local API binds to IPv4; some browsers resolve localhost to ::1 first.
const baseURL = configuredBaseURL.replace(/^(https?:\/\/)localhost(?=[:/])/i, (_match, protocol) => `${protocol}127.0.0.1`)
export const api = axios.create({ baseURL, timeout: 45000 })
let accessToken = null
export const setAccessToken = (token) => { accessToken = token }
let refreshPromise
api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})
api.interceptors.response.use((response) => response, async (error) => {
  const original = error.config || {}
  const refresh = sessionStorage.getItem('ri_refresh_token')
  if (error.response?.status === 401 && refresh && !original._retried && !original.url?.includes('/auth/refresh')) {
    original._retried = true
    try {
      refreshPromise ||= api.post('/auth/refresh', { refresh_token: refresh }).finally(() => { refreshPromise = null })
      const { data } = await refreshPromise
      setAccessToken(data.access_token)
      sessionStorage.setItem('ri_refresh_token', data.refresh_token)
      original.headers = { ...original.headers, Authorization: `Bearer ${data.access_token}` }
      return api(original)
    } catch {
      setAccessToken(null)
      sessionStorage.removeItem('ri_refresh_token')
      window.dispatchEvent(new Event('ri:session-expired'))
    }
  }
  return Promise.reject(error)
})

export function errorMessage(error) {
  if (error instanceof SyntaxError) return 'Skill labels must be valid JSON.'
  if (error.message === 'Skill labels must be a JSON object.') return error.message
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') return 'This search took longer than expected. Check Search history before retrying, since it may have completed on the server.'
  const status = error.response?.status
  const detail = error.response?.data?.detail || error.response?.data?.error?.message
  if (status === 401) return 'Your session has expired. Please sign in again.'
  if (status === 403) return 'You don’t have permission to access this information.'
  if (status === 404) return 'We couldn’t find that resource.'
  if (status === 422) return typeof detail === 'string' ? detail : 'Please check the fields and try again.'
  if (status === 429) return 'Too many requests. Wait a moment and try again.'
  if (status >= 500) return 'The service is having trouble. Please try again.'
  if (!error.response) return 'We couldn’t connect to the service. Check your connection and retry.'
  return typeof detail === 'string' ? detail : 'Something went wrong. Please try again.'
}
