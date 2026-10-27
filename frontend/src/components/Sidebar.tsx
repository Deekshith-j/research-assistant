// Left column: brand, demo user selector, the user's conversations, and backend status.

import type { DemoUser, Session, Status } from '../types'
import ConfirmButton from './ConfirmButton'
import { LogoMark, PlusIcon, TrashIcon } from './icons'

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

/** Relative day label for the conversation list: "Today 14:05", "Yesterday", "27 Oct". */
function dayLabel(iso: string): string {
  const d = new Date(iso)
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000)
  if (days < 1 && new Date().getDate() === d.getDate()) {
    return `Today ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`
  }
  if (days < 2) return 'Yesterday'
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export default function Sidebar(props: Props) {
  const { users, userId, sessions, sessionId, status } = props
  const current = users.find(u => u.id === userId)

  return (
    <aside className="sidebar" aria-label="Conversations">
      <div className="brand">
        <span className="brand-mark"><LogoMark size={18} /></span>
        <div>
          <strong>Asterline</strong>
          <span>Research assistant</span>
        </div>
      </div>

      {/* Demo account switcher: every stored item belongs to the selected user only. */}
      <label className="account">
        <span className="avatar" aria-hidden>{current?.name.slice(0, 1) ?? '?'}</span>
        <span className="account-text">
          <span className="account-name">{current?.name ?? 'Loading…'}</span>
          <span className="account-role">{current?.role ?? ''} · demo user</span>
        </span>
        <select value={userId} onChange={e => props.onUserChange(e.target.value)} aria-label="Switch demo user">
          {users.map(u => <option key={u.id} value={u.id}>{u.name} · {u.role}</option>)}
        </select>
      </label>

      <button className="btn primary block" onClick={props.onNewConversation}>
        <PlusIcon /> New conversation
      </button>

      <nav className="session-nav" aria-label="Conversation history">
        <div className="label">Conversations</div>
        <ul className="session-list">
          {sessions.map(s => (
            <li key={s.id} className={s.id === sessionId ? 'active' : ''}>
              <button className="session" onClick={() => props.onSelectSession(s.id)} title={s.title}
                aria-current={s.id === sessionId ? 'page' : undefined}>
                <span className="session-title">{s.title.replace(/^["“]/, '')}</span>
                <span className="session-date">{dayLabel(s.updated_at)}</span>
              </button>
              <ConfirmButton className="icon-btn" title="Delete conversation" confirmLabel="Delete"
                onConfirm={() => props.onDeleteConversation(s.id)}>
                <TrashIcon size={15} />
              </ConfirmButton>
            </li>
          ))}
        </ul>
      </nav>

      <footer className="status">
        <span><i className={`dot ${status?.llm ? 'ok' : 'bad'}`} /> Groq model {status?.llm ? 'connected' : 'missing key'}</span>
        <span><i className={`dot ${status?.tracing ? 'ok' : 'off'}`} /> LangSmith {status?.tracing ? 'tracing' : 'off'}</span>
      </footer>
    </aside>
  )
}
