// One conversation: message history, the composer, and a pending state while the agents work.

import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Message } from '../types'
import AnswerMessage from './AnswerMessage'
import SourcePanel from './SourcePanel'

const EXAMPLES = [
  'What is the weekly on-call stipend?',
  'What caused INC-2025-12?',
  'I support EU customers on the Team plan.',
  'When will the Asia-Pacific region launch?',
]

interface Props {
  userId: string
  sessionId: string
  onTurnComplete: () => void
}

export default function ChatView({ userId, sessionId, onTurnComplete }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openSource, setOpenSource] = useState<string | null>(null) // chunk id shown in the side panel
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load the stored transcript (it survives restarts; it lives in SQLite).
  useEffect(() => {
    api.messages(userId, sessionId).then(setMessages).catch(e => setError(e.message))
  }, [userId, sessionId])

  // Keep the newest message in view.
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, pending])

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
      setError((e as Error).message)
      setMessages(await api.messages(userId, sessionId).catch(() => []))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="chat">
      <div className="messages">
        {messages.length === 0 && !pending && (
          <div className="empty">
            <h2>Ask about Asterline's documentation</h2>
            <p>Answers cite the source passages. Tell me about yourself and I'll remember it for later conversations.
              You can review it in the Memory tab.</p>
            <div className="examples">
              {EXAMPLES.map(q => <button key={q} className="chip-btn" onClick={() => send(q)}>{q}</button>)}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user'
            ? <div key={i} className="msg user"><div className="bubble">{m.content}</div></div>
            : <AnswerMessage key={i} message={m} onOpenSource={setOpenSource} />,
        )}

        {pending && (
          <div className="msg assistant">
            <div className="bubble pending">
              <span className="spinner" aria-hidden /> Agents are researching… usually 10–30 seconds
            </div>
          </div>
        )}
        {error && <div className="banner error">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={e => { e.preventDefault(); send(draft) }}>
        <textarea
          value={draft}
          placeholder="Ask a question, or tell me what to remember / forget…"
          rows={1}
          disabled={pending}
          onChange={e => setDraft(e.target.value)}
          // Enter sends, Shift+Enter adds a new line.
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(draft) } }}
        />
        <button className="btn primary" type="submit" disabled={pending || !draft.trim()}>Send</button>
      </form>

      {openSource && <SourcePanel chunkId={openSource} onClose={() => setOpenSource(null)} />}
    </section>
  )
}
