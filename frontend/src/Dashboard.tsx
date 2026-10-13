import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  FileSearch,
  FileText,
  Gauge,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
  Zap,
} from 'lucide-react'
import './App.css'

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

type DashboardSummary = {
  project: string
  case_id: string
  status: string
  finding_count: number
  counts: Record<string, number>
  source?: string
}

type Investigation = {
  case_id: string
  audit_status: string
  supervisor_decision: string
  supervisor_reason: string
  retry_count: number
  case_count: number
  created_at: string | null
}

type Evidence = {
  evidence_id: string
  source: string
  description: string
}

type AgentResult = {
  status?: string
  summary?: string
  evidence_reviewed?: Evidence[]
  findings?: unknown[]
  limitations?: string[]
  recommended_next_steps?: string[]
}

type InvestigationDetail = Investigation & {
  summary?: {
    errors?: string[]
    agent_names?: string[]
    agent_results?: Record<string, AgentResult>
  }
  investigation_cases?: Array<{
    group_key: string
    customer_id: string | null
    finding_count: number
    categories: string[]
    finding_ids: string[]
    invoice_line_ids: string[]
    findings: Array<Record<string, unknown>>
    evidence: Evidence[]
    requires_review: boolean
  }>
}

type ReconciliationCase = {
  case_id: string
  status: string
  finding_count: number
  created_at: string
}

type Page = 'overview' | 'investigations' | 'reconciliation'

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options?.headers || {}),
      ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
    },
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Keep the HTTP status message if the response isn't JSON.
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
}

function labelize(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function StatusPill({ value }: { value: string }) {
  const normalized = value.toLowerCase()
  const tone = normalized.includes('complete') || normalized === 'resolved'
    ? 'success'
    : normalized.includes('review') || normalized.includes('unresolved')
      ? 'warning'
      : normalized.includes('fail') || normalized.includes('error')
        ? 'danger'
        : 'neutral'

  return (
    <span className={`status-pill ${tone}`}>
      <span className="status-dot" />
      {labelize(value || 'unknown')}
    </span>
  )
}

export default function Dashboard() {
  const [page, setPage] = useState<Page>('overview')
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null)
  const [investigations, setInvestigations] = useState<Investigation[]>([])
  const [reconciliationCases, setReconciliationCases] = useState<ReconciliationCase[]>([])
  const [selected, setSelected] = useState<InvestigationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [mobileMenu, setMobileMenu] = useState(false)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [summary, runs, cases] = await Promise.all([
        api<DashboardSummary>('/api/v1/dashboard/summary'),
        api<Investigation[]>('/api/v1/investigations'),
        api<ReconciliationCase[]>('/api/v1/reconciliation/cases'),
      ])
      setDashboard(summary)
      setInvestigations(runs)
      setReconciliationCases(cases)
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message}. Check that the FastAPI backend is running at ${API_BASE}.`
          : 'Could not load MeterMind data.',
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  const openInvestigation = async (caseId: string) => {
    setError('')
    try {
      const detail = await api<InvestigationDetail>(
        `/api/v1/investigations/${encodeURIComponent(caseId)}`,
      )
      setSelected(detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load investigation.')
    }
  }

  const runInvestigation = async () => {
    setRunning(true)
    setError('')
    setNotice('')
    try {
      const result = await api<{
        case_id: string
        persistence?: { run_saved?: boolean }
      }>('/api/v1/investigations/run', { method: 'POST' })

      setNotice(
        `Investigation ${result.case_id} finished. Results have been refreshed.`,
      )
      await loadDashboard()
      await openInvestigation(result.case_id)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'The investigation could not be completed.',
      )
    } finally {
      setRunning(false)
    }
  }

  const filteredInvestigations = investigations.filter((item) =>
    `${item.case_id} ${item.audit_status} ${item.supervisor_decision}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  const totalFindings = dashboard?.finding_count ?? 0
  const reviewCount = investigations.filter((item) =>
    `${item.audit_status} ${item.supervisor_decision}`.toLowerCase().includes('review'),
  ).length
  const completedCount = investigations.filter((item) =>
    item.audit_status.toLowerCase().includes('complete'),
  ).length

  const policyEvidence = selected?.summary?.agent_results
    ? Object.entries(selected.summary.agent_results).flatMap(([agent, result]) =>
        (result.evidence_reviewed || [])
          .filter((evidence) => evidence.source === 'billing_policy_rag')
          .map((evidence) => ({ ...evidence, agent })),
      )
    : []

  const deterministicEvidence = selected?.summary?.agent_results
    ? Object.entries(selected.summary.agent_results).flatMap(([agent, result]) =>
        (result.evidence_reviewed || [])
          .filter((evidence) => evidence.source === 'deterministic_pricing_reconstruction')
          .map((evidence) => ({ ...evidence, agent })),
      )
    : []

  return (
    <div className="app-shell">
      {mobileMenu && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileMenu(false)}
        />
      )}

      <aside className={`sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <Link className="brand-mark" to="/" aria-label="MeterMind home">
            <Gauge size={22} />
          </Link>
          <div>
            <div className="brand-name">metermind<span>.</span></div>
            <div className="brand-subtitle">BILLING INTELLIGENCE</div>
          </div>
          <button
            className="icon-button sidebar-close"
            onClick={() => setMobileMenu(false)}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <nav className="navigation">
          <button
            className={`nav-item ${page === 'overview' ? 'active' : ''}`}
            onClick={() => { setPage('overview'); setSelected(null); setMobileMenu(false) }}
          >
            <LayoutDashboard size={18} /> Overview
          </button>
          <button
            className={`nav-item ${page === 'investigations' ? 'active' : ''}`}
            onClick={() => { setPage('investigations'); setSelected(null); setMobileMenu(false) }}
          >
            <FileSearch size={18} /> Investigations
            <span className="nav-count">{investigations.length}</span>
          </button>
          <button
            className={`nav-item ${page === 'reconciliation' ? 'active' : ''}`}
            onClick={() => { setPage('reconciliation'); setSelected(null); setMobileMenu(false) }}
          >
            <FileText size={18} /> Reconciliation
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-heading">
              <span className="system-live" />
              SYSTEM OVERVIEW
            </div>
            <div className="system-row">
              <span>API service</span><span className="system-value">Connected*</span>
            </div>
            <div className="system-row">
              <span>Policy engine</span><span className="system-value">RAG enabled</span>
            </div>
            <div className="system-footnote">*API status confirmed when requests succeed.</div>
          </div>
          <div className="profile-row">
            <div className="avatar">MM</div>
            <div className="profile-text">
              <strong>MeterMind</strong>
              <span>Billing operations</span>
            </div>
            <ShieldCheck size={18} className="profile-shield" />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button
            className="icon-button mobile-menu-button"
            onClick={() => setMobileMenu(true)}
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumbs">
            <span>Workspace</span><ChevronRight size={14} />
            <strong>
              {selected ? 'Investigation details' : labelize(page)}
            </strong>
          </div>
          <div className="topbar-actions">
            <div className="environment"><span /> LOCAL ENVIRONMENT</div>
            <button className="icon-button refresh-button" onClick={() => void loadDashboard()} title="Refresh data">
              <RefreshCw size={17} />
            </button>
            <div className="topbar-avatar">MM</div>
          </div>
        </header>

        <div className="content">
          {error && (
            <div className="alert alert-error">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button className="alert-close" onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button>
            </div>
          )}
          {notice && (
            <div className="alert alert-success">
              <CheckCircle2 size={18} /><span>{notice}</span>
              <button className="alert-close" onClick={() => setNotice('')} aria-label="Dismiss notice"><X size={16} /></button>
            </div>
          )}

          {selected ? (
            <section className="detail-page">
              <button className="back-link" onClick={() => setSelected(null)}>
                ← Back to investigations
              </button>
              <div className="page-heading detail-heading">
                <div>
                  <div className="eyebrow">INVESTIGATION RECORD</div>
                  <h1>{selected.case_id}</h1>
                  <p>Review findings, agent results, and the evidence captured for this run.</p>
                </div>
                <StatusPill value={selected.audit_status} />
              </div>

              <div className="detail-summary-grid">
                <div className="detail-summary-card">
                  <span>Supervisor decision</span>
                  <strong>{labelize(selected.supervisor_decision || 'unknown')}</strong>
                </div>
                <div className="detail-summary-card">
                  <span>Grouped cases</span>
                  <strong>{selected.case_count ?? selected.investigation_cases?.length ?? 0}</strong>
                </div>
                <div className="detail-summary-card">
                  <span>Retry count</span>
                  <strong>{selected.retry_count ?? 0}</strong>
                </div>
                <div className="detail-summary-card">
                  <span>Created</span>
                  <strong className="date-value">{formatDate(selected.created_at)}</strong>
                </div>
              </div>

              {selected.supervisor_reason && (
                <div className="reason-card">
                  <div className="section-icon"><CircleHelp size={18} /></div>
                  <div><strong>Supervisor reasoning</strong><p>{selected.supervisor_reason}</p></div>
                </div>
              )}

              <div className="section-heading">
                <div><h2>Agent results</h2><p>Structured results saved by the investigation workflow.</p></div>
              </div>
              <div className="agent-grid">
                {Object.entries(selected.summary?.agent_results || {}).map(([name, result]) => (
                  <article className="agent-card" key={name}>
                    <div className="agent-card-top">
                      <div className="agent-icon"><Sparkles size={18} /></div>
                      <StatusPill value={result.status || 'recorded'} />
                    </div>
                    <h3>{labelize(name)}</h3>
                    <p>{result.summary || 'Structured agent result is available.'}</p>
                    <div className="agent-meta">
                      <span>{result.evidence_reviewed?.length || 0} evidence references</span>
                      <span>{result.findings?.length || 0} findings</span>
                    </div>
                    {result.limitations && result.limitations.length > 0 && (
                      <details className="inline-details">
                        <summary>Limitations ({result.limitations.length})</summary>
                        <ul>{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
                      </details>
                    )}
                  </article>
                ))}
              </div>

              <div className="section-heading">
                <div><h2>Policy evidence</h2><p>Billing-policy passages retrieved during the pricing workflow.</p></div>
                <span className="count-chip">{policyEvidence.length} references</span>
              </div>
              {policyEvidence.length ? (
                <div className="evidence-list">
                  {policyEvidence.map((item, index) => (
                    <article className="evidence-card" key={`${item.evidence_id}-${index}`}>
                      <div className="evidence-icon policy-icon"><FileText size={18} /></div>
                      <div className="evidence-body">
                        <div className="evidence-title-row">
                          <strong>{item.evidence_id}</strong><span className="source-chip">RAG POLICY</span>
                        </div>
                        <p>{item.description}</p>
                        <span className="evidence-agent">Captured by {labelize(item.agent)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">
                  <FileSearch size={24} />
                  <strong>No saved policy references</strong>
                  <p>This run may predate the explicit policy retrieval integration, or retrieval may not have returned passages.</p>
                </div>
              )}

              <div className="section-heading">
                <div><h2>Deterministic pricing evidence</h2><p>Pricing reconstruction from the authoritative billing data.</p></div>
                <span className="count-chip">{deterministicEvidence.length} references</span>
              </div>
              {deterministicEvidence.length ? (
                <div className="evidence-list">
                  {deterministicEvidence.map((item, index) => (
                    <article className="evidence-card" key={`${item.evidence_id}-${index}`}>
                      <div className="evidence-icon pricing-icon"><Zap size={18} /></div>
                      <div className="evidence-body">
                        <div className="evidence-title-row">
                          <strong>{item.evidence_id}</strong><span className="source-chip deterministic-chip">DETERMINISTIC</span>
                        </div>
                        <p>{item.description}</p>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact"><FileText size={22} /><p>No pricing references were saved for this run.</p></div>
              )}

              <div className="section-heading">
                <div><h2>Grouped investigation cases</h2><p>Customer-level findings stored with this run.</p></div>
              </div>
              <div className="table-card">
                <div className="table-scroll">
                  <table>
                    <thead><tr><th>Group</th><th>Customer</th><th>Findings</th><th>Categories</th><th>Review</th></tr></thead>
                    <tbody>
                      {(selected.investigation_cases || []).map((item) => (
                        <tr key={item.group_key}>
                          <td className="mono">{item.group_key}</td>
                          <td>{item.customer_id || '—'}</td>
                          <td>{item.finding_count}</td>
                          <td>{item.categories.map(labelize).join(', ') || '—'}</td>
                          <td><StatusPill value={item.requires_review ? 'review_required' : 'completed'} /></td>
                        </tr>
                      ))}
                      {!selected.investigation_cases?.length && (
                        <tr><td colSpan={5} className="table-empty">No grouped cases returned for this investigation.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">BILLING INTELLIGENCE PLATFORM</div>
                  <h1>{page === 'overview' ? 'Good to see you.' : page === 'investigations' ? 'Investigations' : 'Reconciliation'}</h1>
                  <p>
                    {page === 'overview'
                      ? 'Your billing operations, anomalies, and evidence-backed investigations at a glance.'
                      : page === 'investigations'
                        ? 'Explore investigation history and review the evidence behind each decision.'
                        : 'Inspect reconciliation cases produced from the authoritative usage and pricing data.'}
                  </p>
                </div>
                <div className="heading-actions">
                  <button className="button-secondary" onClick={() => void loadDashboard()} disabled={loading}>
                    <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
                  </button>
                  <button className="button-primary" onClick={() => void runInvestigation()} disabled={running}>
                    {running ? <LoaderCircle size={17} className="spin" /> : <Zap size={17} />}
                    {running ? 'Running workflow…' : 'Run investigation'}
                  </button>
                </div>
              </div>

              {loading && !dashboard ? (
                <div className="loading-panel"><LoaderCircle size={24} className="spin" /><span>Loading live MeterMind data…</span></div>
              ) : (
                <>
                  <div className="metrics-grid">
                    <article className="metric-card">
                      <div className="metric-top"><span>Total findings</span><div className="metric-icon purple"><Activity size={19} /></div></div>
                      <div className="metric-value">{dashboard ? totalFindings.toLocaleString() : '—'}</div>
                      <div className="metric-foot"><span className="metric-muted">Current fixture reconciliation</span></div>
                    </article>
                    <article className="metric-card">
                      <div className="metric-top"><span>Saved investigations</span><div className="metric-icon blue"><FileSearch size={19} /></div></div>
                      <div className="metric-value">{investigations.length.toLocaleString()}</div>
                      <div className="metric-foot"><span className="metric-muted">Stored investigation runs</span></div>
                    </article>
                    <article className="metric-card">
                      <div className="metric-top"><span>Require review</span><div className="metric-icon amber"><AlertTriangle size={19} /></div></div>
                      <div className="metric-value">{reviewCount.toLocaleString()}</div>
                      <div className="metric-foot"><span className="metric-muted">Runs marked for review</span></div>
                    </article>
                    <article className="metric-card">
                      <div className="metric-top"><span>Completed runs</span><div className="metric-icon green"><CheckCircle2 size={19} /></div></div>
                      <div className="metric-value">{completedCount.toLocaleString()}</div>
                      <div className="metric-foot"><span className="metric-muted">Based on saved audit status</span></div>
                    </article>
                  </div>

                  <div className="dashboard-grid">
                    <section className="panel findings-panel">
                      <div className="panel-heading">
                        <div><h2>Reconciliation findings</h2><p>Counts returned by the live fixture reconciliation endpoint.</p></div>
                        <span className="live-label"><span /> LIVE API</span>
                      </div>
                      <div className="finding-list">
                        {Object.entries(dashboard?.counts || {}).map(([name, count]) => {
                          const max = Math.max(1, ...Object.values(dashboard?.counts || {}))
                          return (
                            <div className="finding-row" key={name}>
                              <div className="finding-label"><span>{labelize(name)}</span><strong>{count}</strong></div>
                              <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(count > 0 ? 4 : 0, (count / max) * 100)}%` }} /></div>
                            </div>
                          )
                        })}
                        {!Object.keys(dashboard?.counts || {}).length && (
                          <div className="empty-inline">No finding categories were returned.</div>
                        )}
                      </div>
                      <div className="panel-footer">
                        <span>Reconciliation status</span><StatusPill value={dashboard?.status || 'unavailable'} />
                      </div>
                    </section>

                    <section className="panel workflow-panel">
                      <div className="panel-heading">
                        <div><h2>Investigation workflow</h2><p>Specialists and policy-backed analysis</p></div>
                        <div className="workflow-badge"><Sparkles size={15} /> AI-assisted</div>
                      </div>
                      <div className="workflow-steps">
                        <div className="workflow-step">
                          <div className="workflow-step-icon"><Activity size={17} /></div>
                          <div><strong>Event Agent</strong><span>Usage-event anomalies</span></div>
                          <CheckCircle2 size={16} className="step-ready" />
                        </div>
                        <div className="workflow-connector" />
                        <div className="workflow-step">
                          <div className="workflow-step-icon"><Zap size={17} /></div>
                          <div><strong>Pricing Agent</strong><span>Effective-dated reconstruction + RAG</span></div>
                          <Sparkles size={16} className="step-ai" />
                        </div>
                        <div className="workflow-connector" />
                        <div className="workflow-step">
                          <div className="workflow-step-icon"><FileText size={17} /></div>
                          <div><strong>Invoice Agent</strong><span>Invoice discrepancy analysis</span></div>
                          <CheckCircle2 size={16} className="step-ready" />
                        </div>
                        <div className="workflow-connector" />
                        <div className="workflow-step">
                          <div className="workflow-step-icon"><ShieldCheck size={17} /></div>
                          <div><strong>Supervisor</strong><span>Review and final decision</span></div>
                          <CircleHelp size={16} className="step-wait" />
                        </div>
                      </div>
                      <button className="workflow-cta" onClick={() => void runInvestigation()} disabled={running}>
                        {running ? 'Investigation in progress…' : 'Start an investigation'}
                        <ChevronRight size={17} />
                      </button>
                    </section>
                  </div>

                  <section className="panel table-panel">
                    <div className="panel-heading table-panel-heading">
                      <div><h2>{page === 'reconciliation' ? 'Reconciliation cases' : 'Recent investigations'}</h2><p>Open a saved record to inspect its details and evidence.</p></div>
                      <div className="table-actions">
                        <div className="search-box"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search cases…" /></div>
                        {page !== 'investigations' && (
                          <button className="text-button" onClick={() => setPage('investigations')}>All investigations <ChevronRight size={15} /></button>
                        )}
                      </div>
                    </div>
                    <div className="table-scroll">
                      {page === 'reconciliation' ? (
                        <table>
                          <thead><tr><th>Case ID</th><th>Status</th><th>Findings</th><th>Created</th></tr></thead>
                          <tbody>
                            {reconciliationCases.filter((item) => `${item.case_id} ${item.status}`.toLowerCase().includes(search.toLowerCase())).map((item) => (
                              <tr key={item.case_id}>
                                <td className="mono">{item.case_id}</td><td><StatusPill value={item.status} /></td><td>{item.finding_count}</td><td>{formatDate(item.created_at)}</td>
                              </tr>
                            ))}
                            {!reconciliationCases.length && <tr><td colSpan={4} className="table-empty">No persisted reconciliation cases yet. Run reconciliation through the API to create one.</td></tr>}
                          </tbody>
                        </table>
                      ) : (
                        <table>
                          <thead><tr><th>Investigation</th><th>Audit status</th><th>Supervisor decision</th><th>Cases</th><th>Created</th><th /></tr></thead>
                          <tbody>
                            {filteredInvestigations.slice(0, page === 'overview' ? 5 : 100).map((item) => (
                              <tr key={item.case_id}>
                                <td><button className="case-link" onClick={() => void openInvestigation(item.case_id)}><span className="case-icon"><FileSearch size={16} /></span><span><strong>{item.case_id}</strong><small>Billing investigation</small></span></button></td>
                                <td><StatusPill value={item.audit_status} /></td>
                                <td>{labelize(item.supervisor_decision)}</td>
                                <td>{item.case_count}</td>
                                <td className="date-cell">{formatDate(item.created_at)}</td>
                                <td><button className="row-open" onClick={() => void openInvestigation(item.case_id)} aria-label={`Open ${item.case_id}`}><ChevronRight size={17} /></button></td>
                              </tr>
                            ))}
                            {!filteredInvestigations.length && <tr><td colSpan={6} className="table-empty">No matching investigations. Run an investigation to create a saved record.</td></tr>}
                          </tbody>
                        </table>
                      )}
                    </div>
                    <div className="table-bottom">
                      <span>Showing live data from MeterMind API</span>
                      <button className="button-quiet" onClick={() => void loadDashboard()}><RefreshCw size={14} /> Refresh records</button>
                    </div>
                  </section>
                </>
              )}
            </>
          )}

          <footer className="footer">
            <span>MeterMind <span className="footer-dot">·</span> Usage billing intelligence</span>
            <span><span className="footer-live" /> Connected to local API when requests succeed</span>
          </footer>
        </div>
      </main>
    </div>
  )
}