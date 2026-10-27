// An assistant answer: Markdown text with citation chips, a status badge, warnings,
// the list of sources, and the collapsible agent trace.

import Markdown from 'react-markdown'
import type { AnswerStatus, Citation, Message } from '../types'

const STATUS_LABEL: Record<AnswerStatus, string> = {
  answered: 'Answered',
  partial: 'Partly documented',
  insufficient_evidence: 'Not documented',
  conflict: 'Conflicting sources',
  memory: 'Memory',
  chat: 'Chat',
  error: 'Model unavailable',
}

// "[pricing:1]" or "[pricing:1, sla:0]" -> one Markdown link per id, rendered as a chip below.
const CITATION_GROUP = /\[([a-z0-9-]+:\d+(?:\s*[,;]\s*[a-z0-9-]+:\d+)*)\]/g

function linkCitations(text: string): string {
  return text.replace(CITATION_GROUP, (_, group: string) =>
    group.split(/\s*[,;]\s*/).map(id => `[${id}](#cite-${id})`).join(' '))
}

export default function AnswerMessage({ message }: { message: Message }) {
  const { meta } = message
  const status = meta.status
  const sources = new Map<string, Citation>((meta.citations ?? []).map(c => [c.chunk_id, c]))

  return (
    <div className="msg assistant">
      <div className="bubble">
        {status && status !== 'chat' && (
          <span className={`badge status-${status}`}>{STATUS_LABEL[status] ?? status}</span>
        )}

        <div className="markdown">
          <Markdown
            components={{
              // Citation links become chips; hovering shows the document title and date.
              a: ({ href, children }) => {
                if (href?.startsWith('#cite-')) {
                  const id = href.slice('#cite-'.length)
                  const src = sources.get(id)
                  return (
                    <a className="cite" href={`#src-${id}`} title={src ? `${src.title} · ${src.published}` : id}>
                      {children}
                    </a>
                  )
                }
                return <a href={href} target="_blank" rel="noreferrer">{children}</a>
              },
            }}
          >
            {linkCitations(message.content)}
          </Markdown>
        </div>

        {(meta.warnings ?? []).map((w, i) => <div key={i} className="banner warn small">{w}</div>)}

        {sources.size > 0 && (
          <div className="sources">
            <div className="section-label">Sources</div>
            <ul>
              {[...sources.values()].map(c => (
                <li key={c.chunk_id} id={`src-${c.chunk_id}`}>
                  <code>{c.chunk_id}</code> {c.title} <span className="muted">· published {c.published}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {meta.trace && meta.trace.length > 0 && (
          <details className="trace">
            <summary>Agent trace ({meta.trace.length} steps)</summary>
            <ol>{meta.trace.map((t, i) => <li key={i}><code>{t}</code></li>)}</ol>
          </details>
        )}
      </div>
    </div>
  )
}
