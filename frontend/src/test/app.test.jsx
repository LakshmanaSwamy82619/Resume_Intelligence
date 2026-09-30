import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from '../state/ThemeContext'

const state = vi.hoisted(() => ({ user: null, signIn: vi.fn() }))
vi.mock('../state/AuthContext', () => ({ useAuth: () => ({ user: state.user, loading: false, signIn: state.signIn, logout: vi.fn() }) }))
import { RequireAuth } from '../App'
import AuthPage from '../pages/AuthPage'
import { CandidateCard } from '../pages/SearchPage'
import { EmptyState, ErrorState, LoadingState } from '../components/UI'

afterEach(() => { cleanup(); state.user = null; state.signIn.mockReset() })

describe('role protected routes', () => {
  it('sends unauthenticated visitors to sign in', async () => {
    render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/private']}><Routes><Route path="/private" element={<RequireAuth role="hr"><div>private data</div></RequireAuth>} /><Route path="/login" element={<div>Sign in to workspace</div>} /></Routes></MemoryRouter>)
    expect(await screen.findByText('Sign in to workspace')).toBeInTheDocument()
    expect(screen.queryByText('private data')).not.toBeInTheDocument()
  })
  it('prevents an HR user from entering an administrator-only route', async () => {
    state.user = { role: 'hr' }
    render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/admin']}><Routes><Route path="/admin" element={<RequireAuth role="admin"><div>admin data</div></RequireAuth>} /><Route path="/workspace" element={<div>recruiter workspace</div>} /></Routes></MemoryRouter>)
    expect(await screen.findByText('recruiter workspace')).toBeInTheDocument()
    expect(screen.queryByText('admin data')).not.toBeInTheDocument()
  })
})

describe('authentication form', () => {
  it('submits credentials and reports sign-in failures accessibly', async () => {
    state.signIn.mockRejectedValueOnce({ response: { status: 401 } })
    render(<ThemeProvider><MemoryRouter><AuthPage /></MemoryRouter></ThemeProvider>)
    fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'hr@example.test' } })
    fireEvent.change(screen.getByPlaceholderText('Enter your password'), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in to workspace/i }))
    await waitFor(() => expect(state.signIn).toHaveBeenCalledWith('hr@example.test', 'wrong-password'))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')
  })
  it('toggles password visibility with an accessible label', () => {
    render(<ThemeProvider><MemoryRouter><AuthPage /></MemoryRouter></ThemeProvider>)
    const password = screen.getByPlaceholderText('Enter your password')
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
  })
})

describe('candidate and request states', () => {
  it('renders grounded evidence with source and page attribution', () => {
    render(<CandidateCard item={{ rank: 1, candidate_id: 'c1', candidate_name: 'Test candidate', final_score: 0.91, score_breakdown: {}, matched_requirements: [], partial_requirements: [], missing_requirements: [], relevant_projects: [], relevant_experience: [], why_selected_summary: 'Relevant experience.', why_selected_points: [], evidence: [{ evidence_text: 'Built production search APIs.', source_file: 'resume.pdf', page_number: 3, resume_id: 'resume-1' }], validation_status: 'validated', validation_notes: [] }} selected={false} onToggle={() => {}} onOpen={() => {}} />)
    fireEvent.click(screen.getByText('Evidence from resume'))
    expect(screen.getByText('“Built production search APIs.”')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open this PDF page' })).toBeInTheDocument()
    expect(screen.getByText('resume.pdf · Page 3')).toBeInTheDocument()
  })
  it('renders loading, empty, and retryable error states', () => {
    const retry = vi.fn()
    const { rerender } = render(<LoadingState label="Loading candidates" />)
    expect(screen.getByText('Loading candidates')).toBeInTheDocument()
    rerender(<EmptyState title="No candidates" text="Upload a resume to begin." />)
    expect(screen.getByText('Upload a resume to begin.')).toBeInTheDocument()
    rerender(<ErrorState error="Service unavailable" retry={retry} />)
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    expect(retry).toHaveBeenCalledOnce()
  })
})
