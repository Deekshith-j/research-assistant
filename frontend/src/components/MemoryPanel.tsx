// Memory inspector: see, correct, forget and add what the assistant remembers about the
// selected user. Editing a memory is a *correction* (the old text becomes "superseded");
// forgetting deletes it permanently together with its history.

import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { DemoUser, Memory, MemoryEvent, MemoryKind } from '../types'

const KINDS: { kind: MemoryKind; label: string; hint: string }[] = [
  { kind: 'profile', label: 'Profile', hint: 'Role, team, customers you support' },
  { kind: 'preference', label: 'Preferences', hint: 'How you like answers' },
  { kind: 'work_context', label: 'Ongoing work', hint: 'Investigations to continue later' },
]

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function MemoryPanel({ user }: { user: DemoUser }) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [superseded, setSuperseded] = useState<Memory[]>([])
  const [events, setEvents] = useState<MemoryEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  // Fetch active memories, the full list (for superseded ones) and the audit log together.
  const load = useCallback(
    () => Promise.all([api.memories(user.id), api.memories(user.id, true), api.memoryEvents(user.id)]),
    [user.id],
  )
  const apply = ([active, all, ev]: [Memory[], Memory[], MemoryEvent[]]) => {
    setMemories(active)
    setSuperseded(all.filter(m => m.status === 'superseded'))
    setEvents(ev)
  }

  useEffect(() => {
    load().then(apply).catch(e => setError(e.message))
  }, [load])

  /** Run a change, show the backend's message on failure (e.g. policy rejection), then refresh. */
  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try { await action() } catch (e) { setError((e as Error).message) }
    apply(await load())
  }

  return (
    <section className="memory">
      <div className="memory-head">
        <div>
          <h2>What I remember about {user.name}</h2>
          <p className="muted">
            Memories personalise answers but are never used as evidence for company facts.
            Only {user.name} can see them. Secrets and sensitive personal details are never stored.
          </p>
        </div>
        {memories.length > 0 && (
          <button className="btn danger"
            onClick={() => confirm(`Forget everything about ${user.name}? This cannot be undone.`)
              && run(() => api.forgetAll(user.id))}>
            Forget everything
          </button>
        )}
      </div>

      {error && <div className="banner error">{error}</div>}

      <div className="memory-groups">
        {KINDS.map(({ kind, label, hint }) => {
          const items = memories.filter(m => m.kind === kind)
          return (
            <div key={kind} className="memory-group">
              <div className="group-head"><h3>{label}</h3><span className="muted">{hint}</span></div>
              {items.length === 0 && <p className="muted empty-group">Nothing yet.</p>}
              {items.map(m => (
                <MemoryCard key={m.id} memory={m}
                  onSave={text => run(() => api.correctMemory(user.id, m.id, text))}
                  onForget={() => run(() => api.forgetMemory(user.id, m.id))} />
              ))}
            </div>
          )
        })}
      </div>

      <AddMemoryForm onAdd={(kind, text) => run(() => api.addMemory(user.id, kind, text))} />

      <details className="history">
        <summary>Correction history and audit log</summary>
        <h4>Superseded memories</h4>
        <p className="muted">Kept so you can see what changed; never shown to the agents. Forgetting a memory removes these too.</p>
        {superseded.length === 0 ? <p className="muted">None.</p> : (
          <ul>{superseded.map(m => <li key={m.id}><s>{m.content}</s> <span className="muted">· {when(m.updated_at)}</span></li>)}</ul>
        )}
        <h4>Recent events</h4>
        <p className="muted">Text of forgotten memories is erased from this log.</p>
        <table>
          <thead><tr><th>When</th><th>Action</th><th>Memory</th><th>Detail</th></tr></thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i}><td>{when(e.created_at)}</td><td>{e.action}</td><td><code>{e.memory_id ?? '—'}</code></td><td>{e.detail ?? '—'}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}

/** One memory with inline editing. */
function MemoryCard({ memory, onSave, onForget }: {
  memory: Memory
  onSave: (text: string) => Promise<void>
  onForget: () => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(memory.content)

  if (editing) {
    return (
      <div className="memory-card editing">
        <textarea value={text} rows={2} onChange={e => setText(e.target.value)} autoFocus />
        <div className="row">
          <button className="btn primary" disabled={!text.trim() || text.trim() === memory.content}
            onClick={async () => { await onSave(text.trim()); setEditing(false) }}>Save correction</button>
          <button className="btn" onClick={() => { setText(memory.content); setEditing(false) }}>Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="memory-card">
      <p>{memory.content}</p>
      <div className="row">
        <span className="muted small">{memory.supersedes ? 'corrected' : 'added'} {when(memory.updated_at)}</span>
        <button className="btn ghost" onClick={() => setEditing(true)}>Edit</button>
        <button className="btn ghost danger" onClick={() => confirm('Forget this memory permanently?') && onForget()}>Forget</button>
      </div>
    </div>
  )
}

/** Manually add a memory (it goes through the same policy gate as the Memory Agent). */
function AddMemoryForm({ onAdd }: { onAdd: (kind: MemoryKind, text: string) => Promise<void> }) {
  const [kind, setKind] = useState<MemoryKind>('profile')
  const [text, setText] = useState('')
  return (
    <form className="add-memory" onSubmit={async e => { e.preventDefault(); await onAdd(kind, text.trim()); setText('') }}>
      <h3>Add a memory</h3>
      <div className="row">
        <select value={kind} onChange={e => setKind(e.target.value as MemoryKind)}>
          {KINDS.map(k => <option key={k.kind} value={k.kind}>{k.label}</option>)}
        </select>
        <input value={text} onChange={e => setText(e.target.value)} placeholder="e.g. Prefers short bullet-point answers" />
        <button className="btn primary" type="submit" disabled={!text.trim()}>Remember</button>
      </div>
    </form>
  )
}
