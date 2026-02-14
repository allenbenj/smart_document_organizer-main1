import { useEffect, useMemo, useState } from 'react'

type StepStatusItem = {
  name: string
  status: string
  updated_at?: string
}

type JobStatus = {
  job_id: string
  workflow: string
  status: string
  current_step: string
  progress: number
  draft_state: string
  updated_at?: string
  stepper?: StepStatusItem[]
  metadata?: Record<string, any>
}

type ProposalRow = {
  proposal_id?: number
  file_id?: number
  current_path?: string
  proposed_folder?: string
  proposed_filename?: string
  confidence?: number
  draft_state?: string
}

const steps = ['sources', 'index_extract', 'summarize', 'proposals', 'review', 'apply', 'analytics']

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(body?.detail || body?.error || `HTTP ${res.status}`)
  }
  return body as T
}

export function App() {
  const [job, setJob] = useState<JobStatus | null>(null)
  const [proposals, setProposals] = useState<ProposalRow[]>([])
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState('Idle')

  const hasPrev = offset > 0
  const hasNext = proposals.length === 10

  const progressPct = useMemo(() => Math.round((job?.progress || 0) * 100), [job])

  const refreshJob = async (jobId: string) => {
    const data = await api<{ success: boolean; job: JobStatus }>(`/api/workflow/jobs/${jobId}/status`)
    setJob(data.job)
    localStorage.setItem('workflowJobId', data.job.job_id)
  }

  const createOrResume = async () => {
    setLoading(true)
    setError(null)
    try {
      const existing = localStorage.getItem('workflowJobId')
      if (existing) {
        await refreshJob(existing)
        setStatusMsg(`Resumed job ${existing}`)
      } else {
        const key = crypto.randomUUID()
        const data = await api<{ success: boolean; job: JobStatus }>(`/api/workflow/jobs`, {
          method: 'POST',
          headers: { 'Idempotency-Key': key },
          body: JSON.stringify({ workflow: 'memory_first_v2' }),
        })
        setJob(data.job)
        localStorage.setItem('workflowJobId', data.job.job_id)
        setStatusMsg(`Created job ${data.job.job_id}`)
      }
    } catch (e: any) {
      setError(`Create/resume failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const triggerProposals = async () => {
    if (!job?.job_id) return
    setLoading(true)
    setError(null)
    try {
      const key = crypto.randomUUID()
      await api(`/api/workflow/jobs/${job.job_id}/steps/proposals/execute`, {
        method: 'POST',
        headers: { 'Idempotency-Key': key },
        body: JSON.stringify({ payload: { limit: 25 } }),
      })
      setStatusMsg('Proposals step executed')
      await refreshJob(job.job_id)
      await loadProposals(0)
    } catch (e: any) {
      setError(`Execute proposals failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const loadProposals = async (nextOffset = offset) => {
    if (!job?.job_id) return
    setLoading(true)
    setError(null)
    try {
      const data = await api<any>(`/api/workflow/jobs/${job.job_id}/results?step=proposals&limit=10&offset=${nextOffset}`)
      const rows = (data?.result?.items || []).map((x: any) => x.payload || {})
      setProposals(rows)
      setOffset(nextOffset)
      setStatusMsg(`Loaded ${rows.length} proposals`)
    } catch (e: any) {
      setError(`Load proposals failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const existing = localStorage.getItem('workflowJobId')
    if (existing) {
      refreshJob(existing)
        .then(() => setStatusMsg(`Resumed persisted job ${existing}`))
        .catch(() => setError('Failed to resume previous workflow job'))
    }
  }, [])

  return (
    <div className="layout">
      <aside className="leftRail">
        <h2>Workflow v2</h2>
        <p className="sub">Memory-first stepper</p>
        <ol>
          {steps.map((step) => {
            const stepState = job?.stepper?.find((s) => s.name === step)?.status || 'not_started'
            const active = job?.current_step === step
            return (
              <li key={step} style={{ fontWeight: active ? 700 : 400 }}>
                {step} <small>[{stepState}]</small>
              </li>
            )
          })}
        </ol>
      </aside>

      <main className="mainPanel">
        <section className="healthStrip">
          <strong>Status:</strong>
          <span>{job ? `${job.status} (${progressPct}%)` : 'no job'}</span>
          <span>Step: {job?.current_step || 'n/a'}</span>
          <span>Draft: {job?.draft_state || 'n/a'}</span>
          <span>{statusMsg}</span>
        </section>

        <section className="card controls">
          <button onClick={createOrResume} disabled={loading}>Create / Resume Job</button>
          <button onClick={triggerProposals} disabled={loading || !job}>Trigger Proposals Step</button>
          <button onClick={() => loadProposals(0)} disabled={loading || !job}>Load Proposals</button>
        </section>

        {error && <section className="errorBox">{error}</section>}

        <section className="card">
          <h3>Proposals</h3>
          {proposals.length === 0 ? (
            <p>No proposal results yet.</p>
          ) : (
            <table className="resultsTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>File</th>
                  <th>Destination</th>
                  <th>Confidence</th>
                  <th>Draft-state</th>
                </tr>
              </thead>
              <tbody>
                {proposals.map((p, idx) => (
                  <tr key={`${p.proposal_id || idx}`}>
                    <td>{p.proposal_id || '-'}</td>
                    <td title={p.current_path}>{p.file_id || '-'}</td>
                    <td>{p.proposed_folder}/{p.proposed_filename}</td>
                    <td>{typeof p.confidence === 'number' ? p.confidence.toFixed(2) : '-'}</td>
                    <td>{p.draft_state || 'auto'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="pager">
            <button disabled={!hasPrev || loading} onClick={() => loadProposals(Math.max(0, offset - 10))}>Prev</button>
            <span>Offset {offset}</span>
            <button disabled={!hasNext || loading} onClick={() => loadProposals(offset + 10)}>Next</button>
          </div>
        </section>
      </main>

      <aside className="consolePanel">
        <h3>Run Console</h3>
        <pre>{JSON.stringify(job, null, 2)}</pre>
      </aside>
    </div>
  )
}
