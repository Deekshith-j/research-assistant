// Left column: demo user selector, the user's conversations, and backend status.

import type { DemoUser, Session, Status } from '../types'

interface Props {
  users: DemoUser[]
  userId: string
  onUserChange: (id: string) => void
  sessions: Session[]
  sessionId: string | null
  onSelectSession: (id: string) => void
  onNewConversation: () => void
  onDeleteConversation: (id: string) => void
  status: Status | null
}

/** "2026-10-27T14:05:00+00:00" -> "27 Oct, 14:05" in the viewer's timezone. */
function shortDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export default function Sidebar(props: Props) {
  const { users, userId, sessions, sessionId, status } = props

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/favicon.svg" alt="" width={28} height={28} />
        <div>
          <strong>Asterline</strong>
          <span>Research assistant</span>
        </div>
      </div>

      <label className="field">
        <span>Signed in as (demo)</span>
        <select value={userId} onChange={e => props.onUserChange(e.target.value)}>
          {users.map(u => <option key={u.id} value={u.id}>{u.name} · {u.role}</option>)}
        </select>
      </label>

      <button className="btn primary block" onClick={props.onNewConversation}>+ New conversation</button>

      <div className="section-label">Conversations</div>
      <ul className="session-list">
        {sessions.map(s => (
          <li key={s.id} className={s.id === sessionId ? 'active' : ''}>
            <button className="session" onClick={() => props.onSelectSession(s.id)} title={s.title}>
              <span className="session-title">{s.title}</span>
              <span className="session-date">{shortDate(s.updated_at)}</span>
            </button>
            <button className="icon-btn" aria-label="Delete conversation" title="Delete conversation"
              onClick={() => { if (confirm('Delete this conversation and its messages?')) props.onDeleteConversation(s.id) }}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <div className="status">
        <div><span className={`dot ${status?.llm ? 'ok' : 'bad'}`} /> Groq LLM</div>
        <div><span className={`dot ${status?.tracing ? 'ok' : 'off'}`} /> LangSmith {status?.tracing ? `· ${status.project}` : 'off'}</div>
      </div>
    </aside>
  )
}
