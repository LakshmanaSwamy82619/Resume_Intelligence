import { describe, expect, it, vi } from 'vitest'
import { api, errorMessage } from '../api/client'
import { resumeApi } from '../api/endpoints'

describe('API client', () => {
  it.each([[401, 'Your session has expired'], [403, 'permission'], [404, 'find that resource'], [422, 'check the fields'], [429, 'Too many requests'], [503, 'service is having trouble']])('maps HTTP %i to a user-facing message', (status, message) => {
    expect(errorMessage({ response: { status } })).toContain(message)
  })
  it('uses a clear connection message for network errors', () => {
    expect(errorMessage({ request: {} })).toContain('couldn’t connect')
  })
  it('sends bulk uploads as repeated multipart files to the existing API contract', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { processing_job_id: 'job-1' } })
    await resumeApi.bulkUpload([new File(['a'], 'one.txt'), new File(['b'], 'two.txt')])
    expect(post).toHaveBeenCalledWith('/resumes/bulk-upload', expect.any(FormData), expect.objectContaining({ onUploadProgress: undefined }))
    const body = post.mock.calls[0][1]
    expect(body.getAll('files')).toHaveLength(2)
    post.mockRestore()
  })
})
