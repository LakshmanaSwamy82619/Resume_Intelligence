import { api } from './client'

export const authApi = {
  login: (payload) => api.post('/auth/login', payload),
  me: () => api.get('/auth/me'),
  forgot: (email) => api.post('/auth/forgot-password', { email }),
  verifyOtp: (payload) => api.post('/auth/verify-otp', payload),
  reset: (payload) => api.post('/auth/reset-password', payload),
  changePassword: (payload) => api.post('/auth/change-password', payload),
  firstLoginPassword: (payload) => api.post('/auth/first-login-password', payload),
}
export const profileApi = { get: () => api.get('/profile'), update: (payload) => api.patch('/profile', payload) }
export const resumeApi = {
  upload: (file, onUploadProgress) => { const form = new FormData(); form.append('file', file); return api.post('/resumes/upload', form, { onUploadProgress }) },
  bulkUpload: (files, onUploadProgress) => { const form = new FormData(); files.forEach((file) => form.append('files', file)); return api.post('/resumes/bulk-upload', form, { onUploadProgress }) },
  jobStatus: (id) => api.get(`/resumes/bulk-upload/${id}`),
  candidate: (id) => api.get(`/resumes/candidates/${id}`),
  download: (id) => api.get(`/resumes/${id}/download`, { responseType: 'blob' }),
}
export const candidateApi = { list: (page = 1, page_size = 25, filters = {}) => api.get('/candidates', { params: { page, page_size, ...filters } }) }
export const shortlistApi = {
  list: () => api.get('/shortlists'),
  get: (id) => api.get(`/shortlists/${id}`),
  create: (payload) => api.post('/shortlists', payload),
  rename: (id, name) => api.patch(`/shortlists/${id}`, { name }),
  remove: (id) => api.delete(`/shortlists/${id}`),
  addCandidates: (id, payload) => api.post(`/shortlists/${id}/candidates`, payload),
  updateCandidate: (id, candidateId, payload) => api.patch(`/shortlists/${id}/candidates/${candidateId}`, payload),
  emailCandidate: (id, candidateId) => api.post(`/shortlists/${id}/candidates/${candidateId}/email`),
  removeCandidate: (id, candidateId) => api.delete(`/shortlists/${id}/candidates/${candidateId}`),
}
export const jobApi = {
  create: (payload) => api.post('/jobs', payload),
  upload: (file, title) => { const form = new FormData(); form.append('file', file); if (title) form.append('title', title); return api.post('/jobs/upload', form) },
  list: () => api.get('/jobs'),
  get: (id) => api.get(`/jobs/${id}`),
  updateRequirements: (id, requirements) => api.put(`/jobs/${id}/requirements`, { requirements }),
}
export const searchApi = {
  // Full candidate evaluation can exceed the general API timeout; recent
  // successful searches have taken roughly a minute.
  create: (payload) => api.post('/search', payload, { timeout: 180000 }),
  history: (limit = 50) => api.get('/search', { params: { limit } }),
  get: (id) => api.get(`/search/${id}`),
  compare: (payload) => api.post('/search/compare', payload),
  exportShortlist: (id, payload) => api.post(`/search/${id}/export`, payload, { responseType: 'blob' }),
}
export const hrApi = {
  overview: () => api.get('/hr/overview'),
  searches: (limit = 50) => api.get('/hr/searches', { params: { limit } }),
  evaluation: (id) => api.get(`/hr/searches/${id}/evaluation`),
}
export const evaluationApi = {
  createDataset: (payload) => api.post('/evaluation/datasets', payload),
  addQuery: (id, payload) => api.post(`/evaluation/datasets/${id}/queries`, payload),
  label: (id, payload) => api.post(`/evaluation/queries/${id}/labels`, payload),
  dataset: (id) => api.get(`/evaluation/datasets/${id}`),
  requestRun: (id, payload) => api.post(`/evaluation/datasets/${id}/requests`, payload),
  requests: () => api.get('/evaluation/requests'),
  runRequest: (id) => api.post(`/evaluation/requests/${id}/run`, {}),
  run: (payload) => api.post('/evaluation/run', payload),
}
export const notificationApi = { list: (unread_only = false) => api.get('/notifications', { params: { unread_only } }), markRead: (ids) => api.post('/notifications/mark-read', { notification_ids: ids }) }
export const adminApi = {
  hrUsers: () => api.get('/admin/hr-accounts'),
  createHr: (payload) => api.post('/admin/hr-accounts', payload),
  status: (id, is_active) => api.patch(`/admin/hr-accounts/${id}/status`, { is_active }),
  audit: (params = {}) => api.get('/admin/audit-logs', { params }),
  analytics: () => api.get('/admin/analytics'),
  retrievalMetrics: () => api.get('/admin/retrieval-metrics'),
  searches: (limit = 25, offset = 0) => api.get('/admin/searches', { params: { limit, offset } }),
  health: () => api.get('/admin/system-health'),
}
export const healthApi = { live: () => api.get('/health/live'), ready: () => api.get('/health/ready') }
