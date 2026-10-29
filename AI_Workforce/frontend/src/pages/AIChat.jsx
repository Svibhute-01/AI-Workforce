import { useEffect, useRef, useState } from 'react'
import { AlertCircle, FileText, MessageCircle, Send, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { EmptyState, Skeleton } from '../components/common/States'
import apiService from '../services/api'
import { normalizeAnswer } from '../utils/chatModel'

const SUGGESTIONS = [
  'Summarize the main functional requirements',
  'Which requirements are ambiguous or unclear?',
  'What are the key constraints and risks?',
]

const clock = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

function AIChat() {
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)
  const [projectsError, setProjectsError] = useState('')
  const [projectId, setProjectId] = useState('')
  const [documents, setDocuments] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const endRef = useRef(null)
  const requestToken = useRef(0)

  useEffect(() => {
    apiService.projects.getAll()
      .then((items) => {
        setProjects(items)
        if (items.length) setProjectId(String(items[0].id))
      })
      .catch((requestError) => setProjectsError(requestError.message))
      .finally(() => setProjectsLoading(false))
  }, [])

  useEffect(() => {
    requestToken.current += 1
    setMessages([])
    setIsLoading(false)
    setDocuments(null)
    if (!projectId) return
    apiService.documents.getForProject(projectId).then(setDocuments).catch(() => setDocuments([]))
  }, [projectId])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isLoading])

  const project = projects.find((item) => String(item.id) === String(projectId))

  const send = async (text) => {
    const question = text.trim()
    if (!question || !projectId || isLoading) return
    const token = requestToken.current
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, sender: 'user', text: question, time: clock() }])
    setInput('')
    setIsLoading(true)
    try {
      const reply = normalizeAnswer(await apiService.rag.query(projectId, question))
      if (token !== requestToken.current) return
      setMessages((prev) => [...prev, reply.text
        ? { id: `a-${Date.now()}`, sender: 'agent', text: reply.text, sources: reply.sources, time: clock() }
        : { id: `e-${Date.now()}`, sender: 'error', text: 'The server answered, but the reply was in a format this page does not recognise.', question, time: clock() }])
    } catch (requestError) {
      if (token !== requestToken.current) return
      setMessages((prev) => [...prev, { id: `e-${Date.now()}`, sender: 'error', text: requestError.message, question, time: clock() }])
    } finally {
      if (token === requestToken.current) setIsLoading(false)
    }
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    send(input)
  }

  if (projectsLoading) {
    return <Skeleton className="h-[28rem]" />
  }

  if (projectsError) {
    return (
      <div role="alert" className="card flex items-center gap-2 px-4 py-3 text-sm text-red-700"><AlertCircle className="h-4 w-4" />{projectsError}</div>
    )
  }

  if (!projects.length) {
    return <EmptyState icon={MessageCircle} title="No projects to chat about yet" hint="Create a project and upload an SRS. Then you can ask questions about it here." to="/projects" cta="Create a project" />
  }

  const hasDocuments = documents === null || documents.length > 0

  return (
    <div className="flex min-h-[32rem] flex-col gap-6 lg:h-[calc(100vh-8.5rem)] lg:flex-row">
      <aside className="card flex w-full shrink-0 flex-col overflow-hidden lg:w-72">
        <div className="border-b border-border-light p-4">
          <h2 className="text-sm font-extrabold text-text-primary">Project context</h2>
        </div>
        <div className="space-y-4 p-4">
          <label className="block text-xs font-bold uppercase tracking-wide text-text-secondary">
            Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input-field mt-1.5 w-full text-sm normal-case tracking-normal">
              {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          {project?.description && <p className="text-sm text-text-secondary">{project.description}</p>}
          <div className="rounded-xl border border-border-light bg-brand-lemon/60 p-3 text-sm">
            <p className="flex items-center gap-2 font-bold text-text-primary"><FileText className="h-4 w-4 text-primary" />{documents === null ? 'Checking documents…' : `${documents.length} document${documents.length === 1 ? '' : 's'}`}</p>
            {documents !== null && documents.length === 0 && (
              <p className="mt-1 text-xs text-text-secondary">Upload an SRS in <Link to="/documents" className="font-bold text-primary underline">Documents</Link> so answers can be grounded in it.</p>
            )}
          </div>
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-text-secondary">Try asking</p>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => send(suggestion)} disabled={isLoading || !hasDocuments} className="bt-chip justify-start rounded-xl text-left disabled:opacity-50">
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-primary" />{suggestion}
                </button>
              ))}
            </div>
          </div>
        </div>
      </aside>

      <section className="card flex min-h-[26rem] flex-1 flex-col overflow-hidden" aria-label="Project chat">
        <div className="border-b border-border-light p-5">
          <h1 className="text-lg font-extrabold text-text-primary">Project Chat</h1>
          <p className="text-sm text-text-secondary">Ask questions about {project?.name || 'your project'} and get answers from its documents</p>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto bg-brand-cream/30 p-5" aria-live="polite">
          {messages.length === 0 && (
            <div className="flex h-full items-center justify-center text-center">
              <div>
                <div className="bt-icon-bubble mx-auto mb-3 h-14 w-14"><MessageCircle className="h-6 w-6" /></div>
                <p className="font-bold text-text-primary">Start a conversation about {project?.name}</p>
                <p className="mt-1 text-sm text-text-secondary">Answers come from the backend&rsquo;s project knowledge base.</p>
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl p-3.5 shadow-sm sm:max-w-lg ${
                message.sender === 'user'
                  ? 'rounded-br-md border border-brand-deep bg-gradient-to-br from-brand-soft to-brand-golden text-brand-ink'
                  : message.sender === 'error'
                    ? 'rounded-bl-md border border-red-200 bg-red-50 text-red-700'
                    : 'rounded-bl-md border border-border-light bg-brand-lemon text-text-primary'
              }`}>
                <p className="whitespace-pre-wrap text-sm">{message.text}</p>
                {!!message.sources?.length && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {message.sources.map((source) => <span key={source} className="rounded-md bg-brand-custard px-2 py-0.5 text-[11px] font-semibold text-text-secondary">{source}</span>)}
                  </div>
                )}
                <div className="mt-1.5 flex items-center justify-between gap-3 text-xs opacity-80">
                  <span>{message.time}</span>
                  {message.sender === 'error' && <button type="button" onClick={() => send(message.question)} className="font-bold underline">Retry</button>}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start" role="status" aria-label="Waiting for an answer">
              <div className="rounded-2xl rounded-bl-md border border-border-light bg-brand-lemon p-3.5">
                <div className="flex gap-1.5">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-deep" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-deep [animation-delay:150ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-brand-deep [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={handleSubmit} className="border-t border-border-light p-4 sm:p-5">
          <div className="flex gap-3">
            <input
              type="text"
              aria-label="Your question"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={hasDocuments ? 'Ask about requirements, scope, risks…' : 'Upload a document first'}
              disabled={!hasDocuments}
              className="input-field flex-1"
            />
            <button type="submit" disabled={isLoading || !input.trim() || !hasDocuments} aria-label="Send message" className="btn-primary flex items-center gap-2">
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

export default AIChat
