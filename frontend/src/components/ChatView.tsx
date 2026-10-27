// One conversation: message history, the composer, and a pending state while the agents work.

import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Message } from '../types'
import AnswerMessage from './AnswerMessage'
import { SendIcon } from './icons'
import SourcePanel from './SourcePanel'

// Starter questions, grouped by what they demonstrate.
const STARTERS = [
  { label: 'Conflicting documents', q: 'What is the weekly on-call stipend?' },
  { label: 'Incident analysis', q: 'What caused INC-2025-12?' },
  { label: 'Remember me', q: 'I support EU customers on the Team plan.' },
  { label: 'Honest gaps', q: 'When will the Asia-Pacific region launch?' },
]

interface Props {
  userId: string
  sessionId: string
  onTurnComplete: () => void
}

export default function ChatView({ userId, sessionId, onTurnComplete }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loaded, setLoaded] = useState(false)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openSource, setOpenSource] = useState<string | null>(null) // chunk id shown in the side panel
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Load the stored transcript (it survives restarts; it lives in SQLite).
  useEffect(() => {
    api.messages(userId, sessionId)
      .then(m => { setMessages(m); setLoaded(true) })
      .catch(e => setError(e.message))
  }, [userId, sessionId])

  // Keep the newest message in view.
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, pending])

  // Grow the composer with its content (up to the CSS max-height).
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [draft])

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || pending) return
    setDraft('')
    setError(null)
    setPending(true)
    // Show the question immediately; the stored (redacted) version replaces it after the turn.
    setMessages(m => [...m, { role: 'user', content: question, meta: {}, created_at: new Date().toISOString() }])
    try {
      await api.ask(userId, sessionId, question)
      setMessages(await api.messages(userId, sessionId))
      onTurnComplete() // the conversation title/order may have changed
    } catch (e) {
      setError(`The request failed: ${(e as Error).message}. Please try again.`)
      setMessages(await api.messages(userId, sessionId).catch(() => []))
    } finally {
      setPending(false)
      inputRef.current?.focus()
    }
  }

  return (
    <section className="chat" aria-label="Conversation">
      <div className="messages">
        {loaded && messages.length === 0 && !pending && (
          <div className="empty">
            <h1>What do you want to find out?</h1>
            <p>
              Answers come only from Asterline's documentation, with every fact cited. Tell me about your role or
              current work and I'll remember it for later conversations. You can review that in Memory.
            </p>
            <div className="starters">
              {STARTERS.map(s => (
                <button key={s.q} className="starter" onClick={() => send(s.q)}>
                  <span className="starter-label">{s.label}</span>
                  <span className="starter-q">{s.q}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user'
            ? <div key={i} className="msg user"><div className="bubble">{m.content}</div></div>
            : <AnswerMessage key={i} message={m} onOpenSource={setOpenSource} />,
        )}

        {/* Skeleton shaped like an answer while the agents run (a turn takes ~10-30 s). */}
        {pending && (
          <div className="msg assistant" aria-live="polite">
            <article className="answer skeleton">
              <span className="pending-label">Researching the documentation…</span>
              <span className="sk w90" /><span className="sk w75" /><span className="sk w60" />
            </article>
          </div>
        )}
        {error && <div className="banner error" role="alert">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={e => { e.preventDefault(); send(draft) }}>
        <div className="composer-box">
          <textarea
            ref={inputRef}
            value={draft}
            placeholder="Ask about Asterline, or tell me what to remember or forget"
            rows={1}
            disabled={pending}
            aria-label="Message"
            onChange={e => setDraft(e.target.value)}
            // Enter sends, Shift+Enter adds a new line.
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(draft) } }}
          />
          <button className="send" type="submit" disabled={pending || !draft.trim()} aria-label="Send">
            <SendIcon size={18} />
          </button>
        </div>
        <p className="composer-hint">Enter to send · Shift + Enter for a new line · Answers cite their sources</p>
      </form>

      {openSource && <SourcePanel chunkId={openSource} onClose={() => setOpenSource(null)} />}
    </section>
  )
}
