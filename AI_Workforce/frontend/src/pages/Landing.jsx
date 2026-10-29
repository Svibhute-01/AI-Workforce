import { Link } from 'react-router-dom'
import { ArrowRight, Boxes, ClipboardList, Code2, Layers, Upload } from 'lucide-react'
import BrandMark from '../components/brand/BrandMark'
import { OrbitScene } from '../components/brand/AIRobot'
import '../styles/app-theme.css'
import '../styles/landing.css'

const AGENTS = [
  {
    name: 'Requirements Analyst AI',
    icon: ClipboardList,
    text: 'Analyzes uploaded SRS documents, extracts requirements and identifies missing or unclear specifications.',
  },
  {
    name: 'Project Manager AI',
    icon: Layers,
    text: 'Creates project plans, assigns tasks, tracks progress and manages project timelines.',
  },
  {
    name: 'Architect AI',
    icon: Boxes,
    text: 'Turns the approved plan into a system architecture with components, interactions and visual diagrams.',
  },
  {
    name: 'Developer AI',
    icon: Code2,
    text: 'Generates code, assists with implementation and creates development documentation.',
  },
]

const WORKFLOW = [
  { label: 'SRS Upload', icon: Upload },
  { label: 'Requirements Analysis', icon: ClipboardList },
  { label: 'Project Planning', icon: Layers },
  { label: 'System Architecture', icon: Boxes },
  { label: 'AI Development', icon: Code2 },
]

const HOW_STEPS = [
  'Upload a Software Requirements Specification (SRS) PDF to a project.',
  'Specialised agents analyse requirements, plan the work and design the architecture.',
  'Developer AI turns the approved design into code and documentation.',
]

function Landing() {
  return (
    <div className="landing-shell lp-root">
      <header className="lp-nav">
        <Link to="/" className="lp-brand" aria-label="AI Workforce home">
          <BrandMark size={38} />
          <span>AI Workforce</span>
        </Link>
        <nav className="lp-links" aria-label="Page sections">
          <a href="#how">How it works</a>
          <a href="#agents">AI agents</a>
          <a href="#workflow">Workflow</a>
        </nav>
        <div className="lp-actions">
          <Link to="/login" className="lp-signin">Sign In</Link>
          <Link to="/login" state={{ mode: 'register' }} className="lp-cta-small">Get Started</Link>
        </div>
      </header>

      <section className="lp-hero" aria-labelledby="lp-title">
        <div className="lp-glow lp-glow-a" aria-hidden="true" />
        <div className="lp-glow lp-glow-b" aria-hidden="true" />
        <div className="lp-hero-grid">
          <div className="lp-copy">
            <span className="lp-eyebrow">Multi-agent SDLC automation</span>
            <h1 id="lp-title" className="lp-title">
              From Requirements to Reality.
              <span className="lp-title-accent"> Powered by AI.</span>
            </h1>
            <p className="lp-lede">
              An intelligent multi-agent platform that transforms software requirements into structured plans, system architecture, and working software through collaborative AI agents.
            </p>
            <div className="lp-hero-actions">
              <Link to="/login" state={{ mode: 'register' }} className="lp-cta">
                Get Started <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link to="/login" className="lp-ghost">Sign In</Link>
            </div>
          </div>
          <div className="lp-art">
            <OrbitScene />
          </div>
        </div>
        <div className="lp-wave" aria-hidden="true">
          <svg viewBox="0 0 1440 140" preserveAspectRatio="none">
            <path d="M0,74 C230,140 420,22 720,62 C1010,102 1190,28 1440,84 L1440,140 L0,140 Z" fill="#F4F8FF" />
          </svg>
        </div>
      </section>

      <section id="how" className="lp-section">
        <div className="lp-section-head">
          <span className="lp-kicker">How AI Workforce works</span>
          <h2>One workspace from specification to working software</h2>
          <p>Each stage is handled by a dedicated AI agent, so every project moves through the same structured lifecycle.</p>
        </div>
        <ol className="lp-steps">
          {HOW_STEPS.map((step, index) => (
            <li key={step} className="lp-step">
              <span className="lp-step-num">{index + 1}</span>
              <p>{step}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="agents" className="lp-section lp-section-tint">
        <div className="lp-section-head">
          <span className="lp-kicker">The AI team</span>
          <h2>Specialised agents for every SDLC stage</h2>
        </div>
        <div className="lp-agent-grid">
          {AGENTS.map((agent) => {
            const Icon = agent.icon
            return (
              <article key={agent.name} className="lp-agent-card">
                <span className="lp-agent-icon"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                <h3>{agent.name}</h3>
                <p>{agent.text}</p>
              </article>
            )
          })}
        </div>
      </section>

      <section id="workflow" className="lp-section">
        <div className="lp-section-head">
          <span className="lp-kicker">End-to-end SDLC workflow</span>
          <h2>From a single SRS to an implemented system</h2>
        </div>
        <ol className="lp-flow" aria-label="SDLC workflow stages">
          {WORKFLOW.map((stage, index) => {
            const Icon = stage.icon
            return (
              <li key={stage.label} className="lp-flow-item">
                <span className="lp-flow-icon"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                <span className="lp-flow-num">Stage {index + 1}</span>
                <span className="lp-flow-label">{stage.label}</span>
              </li>
            )
          })}
        </ol>
      </section>

      <section className="lp-final">
        <h2>Start turning requirements into working software</h2>
        <div className="lp-hero-actions">
          <Link to="/login" state={{ mode: 'register' }} className="lp-cta">Get Started <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
          <Link to="/login" className="lp-ghost lp-ghost-dark">Sign In</Link>
        </div>
      </section>

      <footer className="lp-footer">
        <span>© AI Workforce · Multi-agent SDLC automation</span>
      </footer>
    </div>
  )
}

export default Landing
