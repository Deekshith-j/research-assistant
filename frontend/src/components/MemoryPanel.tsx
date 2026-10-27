// Memory inspector: see, correct, forget and add what the assistant remembers about the
// selected user. Editing a memory is a *correction* (the old text becomes "superseded");
// forgetting deletes it permanently together with its history.

import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { DemoUser, Memory, MemoryEvent, MemoryKind } from '../types'
import ConfirmButton from './ConfirmButton'
import { ChevronIcon, EditIcon, TrashIcon } from './icons'

const KINDS: { kind: MemoryKind; label: string; hint: string }[] = [
  { kind: 'profile', label: 'Profile', hint: 'Role, team, customers you support' },
  { kind: 'preference', label: 'Preferences', hint: 'How you like answers' },
  { kind: 'work_context', label: 'Ongoing work', hint: 'Investigations to pick up later' },
]

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function MemoryPanel({ user }: { user: DemoUser }) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [superseded, setSuperseded] = useState<Memory[]>([])
  const [events, setEvents] = useState<MemoryEvent[]>([])
  const [loaded, setLoaded] = useState(false)
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
    setLoaded(true)
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
    <section className="memory" aria-label="Memory">
      <div className="memory-inner">
        <header className="memory-head">
          <div>
            <h1>What I remember about {user.name}</h1>
            <p className="muted">
              Memories personalise answers. They are never used as evidence for company facts, only {user.name} can
              see them, and secrets or sensitive personal details are never stored.
            </p>
          </div>
          <div className="memory-count">
            <span className="num">{memories.length}</span>
            <span className="muted small">active</span>
          </div>
        </header>

        {error && <div className="banner error" role="alert">{error}</div>}

        <div className="memory-groups">
          {KINDS.map(({ kind, label, hint }) => {
            const items = memories.filter(m => m.kind === kind)
            return (
              <section key={kind} className="memory-group">
                <header className="group-head">
                  <h2>{label}</h2>
                  <span className="muted small">{hint}</span>
                </header>
                {loaded && items.length === 0 && <p className="empty-group">Nothing remembered yet.</p>}
                {items.map(m => (
                  <MemoryCard key={m.id} memory={m}
                    onSave={text => run(() => api.correctMemory(user.id, m.id, text))}
                    onForget={() => run(() => api.forgetMemory(user.id, m.id))} />
                ))}
              </section>
            )
          })}
        </div>

        <AddMemoryForm onAdd={(kind, text) => run(() => api.addMemory(user.id, kind, text))} />

        <details className="history">
          <summary><ChevronIcon size={14} className="trace-chevron" /> Correction history and audit log</summary>
          <h3>Superseded memories</h3>
          <p className="muted small">Kept so you can see what changed; never shown to the agents. Forgetting a memory removes these too.</p>
          {superseded.length === 0 ? <p className="muted small">None.</p> : (
            <ul className="superseded">
              {superseded.map(m => <li key={m.id}><s>{m.content}</s> <span className="muted small">· {when(m.updated_at)}</span></li>)}
            </ul>
          )}
          <h3>Recent events</h3>
          <p className="muted small">The text of forgotten memories is erased from this log.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>When</th><th>Action</th><th>Memory</th><th>Detail</th></tr></thead>
              <tbody>
                {events.length === 0 && <tr><td colSpan={4} className="muted">No events yet.</td></tr>}
                {events.map((e, i) => (
                  <tr key={i}>
                    <td className="num">{when(e.created_at)}</td>
                    <td><span className={`event event-${e.action}`}>{e.action.replace('_', ' ')}</span></td>
                    <td><code>{e.memory_id ?? '—'}</code></td>
                    <td>{e.detail ?? <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>

        {memories.length > 0 && (
          <div className="danger-zone">
            <div>
              <strong>Forget everything</strong>
              <p className="muted small">Permanently deletes all of {user.name}'s memories and their history.</p>
            </div>
            <ConfirmButton className="btn danger" confirmLabel="Click again to forget all"
              onConfirm={() => run(() => api.forgetAll(user.id))}>
              Forget everything
            </ConfirmButton>
          </div>
        )}
      </div>
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
        <textarea value={text} rows={2} onChange={e => setText(e.target.value)} autoFocus aria-label="Corrected memory" />
        <div className="row">
          <button className="btn primary sm" disabled={!text.trim() || text.trim() === memory.content}
            onClick={async () => { await onSave(text.trim()); setEditing(false) }}>Save correction</button>
          <button className="btn sm" onClick={() => { setText(memory.content); setEditing(false) }}>Cancel</button>
        </div>
      </div>
    )
  }
  return (
    <div className="memory-card">
      <p>{memory.content}</p>
      <div className="row">
        <span className="muted small">{memory.supersedes ? 'Corrected' : 'Added'} {when(memory.updated_at)}</span>
        <button className="btn icon" onClick={() => setEditing(true)} aria-label="Edit memory" title="Edit (saves a correction)">
          <EditIcon size={15} />
        </button>
        <ConfirmButton className="btn icon danger" title="Forget permanently" confirmLabel="Forget"
          onConfirm={onForget}>
          <TrashIcon size={15} />
        </ConfirmButton>
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
      <h2>Add a memory</h2>
      <div className="row">
        <select value={kind} onChange={e => setKind(e.target.value as MemoryKind)} aria-label="Memory type">
          {KINDS.map(k => <option key={k.kind} value={k.kind}>{k.label}</option>)}
        </select>
        <input value={text} onChange={e => setText(e.target.value)} aria-label="Memory text"
          placeholder="e.g. Prefers short bullet-point answers" />
        <button className="btn primary" type="submit" disabled={!text.trim()}>Remember</button>
      </div>
    </form>
  )
}
