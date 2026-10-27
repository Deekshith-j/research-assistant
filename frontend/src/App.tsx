// App shell: owns "who is signed in", "which conversation is open" and "which tab".
// Chat and Memory panels fetch their own data for the current user.

import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import ChatView from './components/ChatView'
import MemoryPanel from './components/MemoryPanel'
import Sidebar from './components/Sidebar'
import type { DemoUser, Session, Status } from './types'

type Tab = 'chat' | 'memory'

export default function App() {
  const [users, setUsers] = useState<DemoUser[]>([])
  const [status, setStatus] = useState<Status | null>(null)
  const [userId, setUserId] = useState<string>(() => localStorage.getItem('userId') ?? 'alice')
  const [sessions, setSessions] = useState<Session[]>([])
  // Open conversation per user: after switching user, nothing of the previous user's
  // selection is used (not even for one render).
  const [openByUser, setOpenByUser] = useState<Record<string, string | null>>({})
  const sessionId = openByUser[userId] ?? null
  const setSessionId = (id: string | null) => setOpenByUser(m => ({ ...m, [userId]: id }))
  const [tab, setTab] = useState<Tab>('chat')
  const [error, setError] = useState<string | null>(null)

  // Static data: demo users and backend status.
  useEffect(() => {
    api.users().then(setUsers).catch(e => setError(e.message))
    api.status().then(setStatus).catch(() => setStatus(null))
  }, [])

  /** Show a fetched conversation list; keep the open one if it still exists, else open `select` or the latest. */
  const applySessions = useCallback((list: Session[], select?: string) => {
    setSessions(list)
    setOpenByUser(m => {
      const wanted = select ?? m[userId]
      const open = wanted && list.some(s => s.id === wanted) ? wanted : (list[0]?.id ?? null)
      return { ...m, [userId]: open }
    })
  }, [userId])

  const refreshSessions = async (select?: string) => {
    const list = await api.sessions(userId)
    applySessions(list, select)
    return list
  }

  // Switching user: load their conversations and continue the latest one
  // (a user with no conversations gets a fresh one).
  useEffect(() => {
    localStorage.setItem('userId', userId)
    api.sessions(userId)
      .then(async list => list.length > 0 ? list : [await api.createSession(userId)])
      .then(list => applySessions(list))
      .catch(e => setError(e.message))
  }, [userId, applySessions])

  const newConversation = async () => {
    const s = await api.createSession(userId)
    await refreshSessions(s.id)
    setTab('chat')
  }

  const deleteConversation = async (id: string) => {
    await api.deleteSession(userId, id)
    const list = await refreshSessions()
    if (list.length === 0) await newConversation()
  }

  const currentUser = users.find(u => u.id === userId)

  return (
    <div className="app">
      <Sidebar
        users={users}
        userId={userId}
        onUserChange={setUserId}
        sessions={sessions}
        sessionId={sessionId}
        onSelectSession={id => { setSessionId(id); setTab('chat') }}
        onNewConversation={newConversation}
        onDeleteConversation={deleteConversation}
        status={status}
      />

      <main className="main">
        <header className="topbar">
          <nav className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'chat'} className={tab === 'chat' ? 'active' : ''}
              onClick={() => setTab('chat')}>Chat</button>
            <button role="tab" aria-selected={tab === 'memory'} className={tab === 'memory' ? 'active' : ''}
              onClick={() => setTab('memory')}>Memory</button>
          </nav>
          {currentUser && <span className="whoami">{currentUser.name} · {currentUser.role}</span>}
        </header>

        {error && <div className="banner error">{error}</div>}
        {status && !status.llm && (
          <div className="banner warn">
            No <code>GROQ_API_KEY</code> configured: answers fall back to the most relevant passages.
            Add a key to <code>.env</code> and restart.
          </div>
        )}

        {tab === 'chat' && sessionId && (
          // `key` remounts the view per conversation, so no state leaks between them.
          <ChatView key={`${userId}:${sessionId}`} userId={userId} sessionId={sessionId}
            onTurnComplete={() => refreshSessions()} />
        )}
        {tab === 'memory' && currentUser && <MemoryPanel key={userId} user={currentUser} />}
      </main>
    </div>
  )
}
