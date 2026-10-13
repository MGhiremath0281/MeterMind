import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  Gauge,
  GitCompareArrows,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import './LandingPage.css'

const features = [
  {
    icon: GitCompareArrows,
    title: 'Usage reconciliation',
    description:
      'Detect duplicate events, missing usage, invoice discrepancies, and calculation errors.',
    tag: 'DETERMINISTIC ENGINE',
  },
  {
    icon: Sparkles,
    title: 'AI-assisted investigation',
    description:
      'Specialist agents investigate anomalies and organize findings for human review.',
    tag: 'MULTI-AGENT WORKFLOW',
  },
  {
    icon: FileSearch,
    title: 'Evidence-backed decisions',
    description:
      'Connect findings to reconstructed invoice lines, source events, and retrieved billing policies.',
    tag: 'TRACEABLE EVIDENCE',
  },
  {
    icon: ShieldCheck,
    title: 'Controlled by design',
    description:
      'A deterministic supervisor routes decisions for review without authorizing financial corrections.',
    tag: 'HUMAN REVIEW',
  },
]

const steps = [
  {
    number: '01',
    title: 'Ingest usage and billing data',
    description:
      'Start with usage events, customer plans, effective-dated pricing, and invoice records.',
  },
  {
    number: '02',
    title: 'Reconcile and investigate',
    description:
      'Reconstruct expected charges and use specialist agents to examine discrepancies.',
  },
  {
    number: '03',
    title: 'Review the evidence',
    description:
      'Inspect findings, policy references, and the supervisor decision in one workspace.',
  },
]

export default function LandingPage() {
  return (
    <main className="landing">
      <nav className="landing-nav">
        <Link className="landing-brand" to="/" aria-label="MeterMind home">
          <span className="brand-mark">
            <Gauge size={25} />
          </span>
          <span>
            <strong>metermind<span>.</span></strong>
            <small>BILLING INTELLIGENCE</small>
          </span>
        </Link>

        <div className="landing-nav-links">
          <a href="#features">Platform</a>
          <a href="#workflow">How it works</a>
        </div>

        <Link className="nav-cta" to="/dashboard">
          Open dashboard <ArrowUpRight size={16} />
        </Link>
      </nav>

      <section className="landing-hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            INTELLIGENCE FOR USAGE-BASED BILLING
          </div>

          <h1>
            Every usage event.
            <br />
            Every invoice.
            <br />
            <span>Accounted for.</span>
          </h1>

          <p className="hero-description">
            MeterMind reconciles SaaS usage and billing data, investigates
            discrepancies with AI-assisted workflows, and connects every
            finding to traceable evidence.
          </p>

          <div className="hero-actions">
            <Link className="primary-cta" to="/dashboard">
              Explore the platform <ArrowRight size={18} />
            </Link>
            <a className="secondary-cta" href="#features">
              Discover capabilities
            </a>
          </div>

          <div className="hero-assurance">
            <CheckCircle2 size={16} />
            Deterministic reconciliation
            <span>·</span>
            Human-reviewed outcomes
          </div>
        </div>

        <div className="hero-visual">
          <div className="visual-glow" />

          <div className="shape-mosaic" aria-hidden="true">
            <span className="s-purple" />
            <span className="s-green" />
            <span className="s-pill" />
            <span className="s-arch" />
            <span className="s-circle" />
            <span className="s-tri-o" />
            <span className="s-tri-y" />
            <span className="s-tri-g" />
          </div>

          <div className="preview-window">
            <div className="preview-topbar">
              <div className="window-dots">
                <i />
                <i />
                <i />
              </div>
              <span>METER MIND / WORKSPACE</span>
              <span className="preview-live">
                <i /> LOCAL DEMO
              </span>
            </div>

            <div className="preview-body">
              <div className="preview-heading">
                <div>
                  <small>RECONCILIATION OVERVIEW</small>
                  <h3>Billing health</h3>
                </div>
                <span className="review-pill">Review required</span>
              </div>

              <div className="preview-stats">
                <div>
                  <span>Total findings</span>
                  <strong>04</strong>
                  <small>Needs investigation</small>
                </div>
                <div>
                  <span>Usage anomalies</span>
                  <strong>02</strong>
                  <small>Duplicate + missing</small>
                </div>
              </div>

              <div className="preview-panel">
                <div className="preview-panel-heading">
                  <span>Finding distribution</span>
                  <span>JUL 2026</span>
                </div>

                {[
                  ['Duplicate events', '01', '72%'],
                  ['Missing events', '01', '72%'],
                  ['Invoice mismatch', '01', '72%'],
                  ['Calculation mismatch', '01', '72%'],
                ].map(([label, count, width]) => (
                  <div className="preview-bar-row" key={label}>
                    <div>
                      <span>{label}</span>
                      <strong>{count}</strong>
                    </div>
                    <div className="preview-track">
                      <span style={{ width }} />
                    </div>
                  </div>
                ))}
              </div>

              <div className="preview-status">
                <span className="status-icon">
                  <ShieldCheck size={18} />
                </span>
                <div>
                  <strong>Supervisor decision</strong>
                  <small>Evidence captured · Human review required</small>
                </div>
                <CheckCircle2 size={17} />
              </div>
            </div>
          </div>

          <div className="floating-chip chip-top">
            <Zap size={16} />
            <span>
              <strong>AI-assisted</strong>
              <small>Investigation workflow</small>
            </span>
          </div>

          <div className="floating-chip chip-bottom">
            <ShieldCheck size={17} />
            Evidence-backed review
          </div>
        </div>
      </section>

      <section className="trust-strip">
        <span>BUILT AROUND FOUR PRINCIPLES</span>
        <div><CheckCircle2 size={16} /> Deterministic calculations</div>
        <div><FileSearch size={16} /> Traceable evidence</div>
        <div><Sparkles size={16} /> AI-assisted analysis</div>
        <div><ShieldCheck size={16} /> Human oversight</div>
      </section>

      <section className="features-section" id="features">
        <div className="section-heading">
          <span className="section-kicker">THE PLATFORM</span>
          <h2>From billing anomalies to explainable investigations.</h2>
          <p>
            One workflow to reconcile usage, investigate discrepancies, and
            prepare evidence for review.
          </p>
        </div>

        <div className="feature-grid">
          {features.map((feature, index) => {
            const Icon = feature.icon

            return (
              <article className="feature-card" key={feature.title}>
                <span className="feature-icon">
                  <Icon size={22} />
                </span>
                <span className="feature-number">
                  0{index + 1} / CAPABILITY
                </span>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
                <span className="feature-tag">{feature.tag}</span>
              </article>
            )
          })}
        </div>
      </section>

      <section className="workflow-section" id="workflow">
        <div className="section-heading">
          <span className="section-kicker">HOW IT WORKS</span>
          <h2>A clear path from raw data to human review.</h2>
        </div>

        <div className="workflow-grid">
          {steps.map((step) => (
            <article className="workflow-step" key={step.number}>
              <span>{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-cta">
        <div>
          <span className="section-kicker">YOUR BILLING WORKSPACE</span>
          <h2>Make every discrepancy explainable.</h2>
          <p>
            Explore the live MeterMind dashboard and inspect the synthetic
            reconciliation and investigation demo.
          </p>
        </div>
        <Link className="primary-cta" to="/dashboard">
          Open MeterMind <ArrowRight size={18} />
        </Link>
      </section>

      <footer className="landing-footer">
        <Link className="landing-brand footer-brand" to="/">
          <span className="brand-mark">
            <Gauge size={20} />
          </span>
          <span>
            <strong>metermind<span>.</span></strong>
            <small>BILLING INTELLIGENCE</small>
          </span>
        </Link>
        <span>Usage billing intelligence · Local demo environment</span>
      </footer>
    </main>
  )
}