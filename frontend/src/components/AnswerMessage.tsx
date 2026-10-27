// An assistant answer: status label, Markdown text with citation chips, warnings,
// the list of sources, and the agent trace rendered as a timeline.

import Markdown from 'react-markdown'
import type { AnswerStatus, Citation, Message } from '../types'
import { ChevronIcon, DocIcon } from './icons'

const STATUS_LABEL: Record<AnswerStatus, string> = {
  answered: 'Answered from documents',
  partial: 'Partly documented',
  insufficient_evidence: 'Not documented',
  conflict: 'Sources disagree',
  memory: 'Memory updated',
  chat: '',
  error: 'Model unavailable · showing passages',
}

// "[pricing:1]" or "[pricing:1, sla:0]" -> one Markdown link per id, rendered as a chip below.
const CITATION_GROUP = /\[([a-z0-9-]+:\d+(?:\s*[,;]\s*[a-z0-9-]+:\d+)*)\]/g

function linkCitations(text: string): string {
  return text.replace(CITATION_GROUP, (_, group: string) =>
    group.split(/\s*[,;]\s*/).map(id => `[${id}](#cite-${id})`).join(' '))
}

// Trace lines look like "Coordinator: route=research | ..." or "ResearchAgent round 1: ...".
// Map the prefix to the agent that wrote it, so the timeline shows who did what.
const AGENTS: [prefix: string, name: string][] = [
  ['MemoryAgent', 'Memory agent'], ['Coordinator', 'Coordinator'], ['ResearchAgent', 'Research agent'],
  ['AnalystAgent', 'Analyst'], ['VerifierAgent', 'Verifier'], ['Responder', 'Responder'],
]

function parseTrace(line: string): { agent: string; step: string; detail: string } {
  const colon = line.indexOf(':')
  const head = colon > 0 ? line.slice(0, colon) : line
  const detail = colon > 0 ? line.slice(colon + 1).trim() : ''
  const match = AGENTS.find(([prefix]) => head.startsWith(prefix))
  const step = match ? head.slice(match[0].length).replace(/^[.\s(]+|\)$/g, '') : ''
  return { agent: match?.[1] ?? head, step, detail }
}

interface Props {
  message: Message
  /** Open the source panel for a chunk id. */
  onOpenSource: (chunkId: string) => void
}

export default function AnswerMessage({ message, onOpenSource }: Props) {
  const { meta } = message
  const status = meta.status
  const sources = new Map<string, Citation>((meta.citations ?? []).map(c => [c.chunk_id, c]))

  return (
    <div className="msg assistant">
      <article className="answer">
        {status && STATUS_LABEL[status] && (
          <div className={`status-label status-${status}`}><i />{STATUS_LABEL[status]}</div>
        )}

        <div className="markdown">
          <Markdown
            components={{
              // Citation links become chips: hover shows title + date, click opens the passage.
              a: ({ href, children }) => {
                if (href?.startsWith('#cite-')) {
                  const id = href.slice('#cite-'.length)
                  const src = sources.get(id)
                  return (
                    <button type="button" className="cite" onClick={() => onOpenSource(id)}
                      title={src ? `${src.title} · ${src.published} (click to read)` : id}>
                      {children}
                    </button>
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
            <div className="label">Sources</div>
            <ul>
              {[...sources.values()].map(c => (
                <li key={c.chunk_id}>
                  <button type="button" className="source-row" onClick={() => onOpenSource(c.chunk_id)}>
                    <DocIcon size={15} />
                    <span className="source-title">{c.title}</span>
                    <code>{c.chunk_id}</code>
                    <span className="source-date">{c.published}</span>
                    <ChevronIcon size={14} className="source-chevron" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {meta.trace && meta.trace.length > 0 && (
          <details className="trace">
            <summary><ChevronIcon size={14} className="trace-chevron" /> How the agents worked · {meta.trace.length} steps</summary>
            <ol className="timeline">
              {meta.trace.map((line, i) => {
                const t = parseTrace(line)
                return (
                  <li key={i}>
                    <span className="tl-agent">{t.agent}{t.step && <em> {t.step}</em>}</span>
                    <span className="tl-detail">{t.detail}</span>
                  </li>
                )
              })}
            </ol>
          </details>
        )}
      </article>
    </div>
  )
}
