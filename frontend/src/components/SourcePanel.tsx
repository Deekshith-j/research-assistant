// Slide-over panel that shows the exact corpus passage behind a citation, so the user can
// check an answer against its evidence without leaving the conversation.

import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Chunk } from '../types'
import { CloseIcon } from './icons'

interface Props {
  chunkId: string
  onClose: () => void
}

export default function SourcePanel({ chunkId, onClose }: Props) {
  const [chunk, setChunk] = useState<Chunk | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.chunk(chunkId).then(setChunk).catch(e => setError(e.message))
  }, [chunkId])

  // Escape closes the panel.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="source-panel" role="dialog" aria-modal="true" aria-label={`Source ${chunkId}`}>
        <header>
          <div>
            <div className="label">Source passage</div>
            <h2>{chunk?.title ?? chunkId}</h2>
          </div>
          <button className="btn icon" onClick={onClose} aria-label="Close source panel" autoFocus>
            <CloseIcon />
          </button>
        </header>

        {error && <div className="banner error small">{error}</div>}
        {!chunk && !error && (
          <div className="skeleton-block"><span className="sk w60" /><span className="sk w90" /><span className="sk w75" /></div>
        )}

        {chunk && (
          <>
            <blockquote className="source-text">{chunk.text}</blockquote>
            <dl className="source-meta">
              <dt>Chunk</dt><dd><code>{chunk.chunk_id}</code></dd>
              <dt>Published</dt><dd className="num">{chunk.published}</dd>
              <dt>Doc version</dt><dd className="num">{chunk.version}</dd>
              <dt>Category</dt><dd>{chunk.category}</dd>
              <dt>Source</dt><dd><code>{chunk.source_url}</code></dd>
            </dl>
            <p className="muted small">Verbatim text from the company knowledge base (data/corpus.jsonl).</p>
          </>
        )}
      </aside>
    </>
  )
}
