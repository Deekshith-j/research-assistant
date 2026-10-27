// Shapes of the JSON returned by the Python API (assistant/api.py).

export interface DemoUser {
  id: string
  name: string
  role: string
}

export interface Status {
  llm: boolean
  tracing: boolean
  project: string
}

export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Citation {
  chunk_id: string
  title: string
  published: string
}

export interface MemoryOp {
  action: 'add' | 'correct' | 'forget' | 'forget_all' | 'unavailable'
  status: 'applied' | 'rejected'
  kind?: string | null
  content?: string | null
  previous?: string | null
  detail?: string | null
}

/** Extra data stored with each assistant message. */
export interface AnswerMeta {
  status?: AnswerStatus
  citations?: Citation[]
  warnings?: string[]
  trace?: string[]
  memory_ops?: MemoryOp[]
  latency_s?: number
}

export type AnswerStatus =
  | 'answered' | 'partial' | 'insufficient_evidence' | 'conflict'
  | 'memory' | 'chat' | 'error'

export interface Message {
  role: 'user' | 'assistant'
  content: string
  meta: AnswerMeta
  created_at: string
}

/** Result of one conversation turn (POST .../messages). */
export interface TurnResult {
  answer: string
  status: AnswerStatus
  citations: Citation[]
  warnings: string[]
  memory_ops: MemoryOp[]
  trace: string[]
  evidence_ids: string[]
  redacted: string[]
  latency_s: number
}

/** One corpus passage, as returned by GET /api/chunks/{id}. */
export interface Chunk {
  chunk_id: string
  doc_id: string
  title: string
  category: string
  owner: string
  source_url: string
  published: string
  version: string
  text: string
}

export type MemoryKind = 'profile' | 'preference' | 'work_context'

export interface Memory {
  id: string
  kind: MemoryKind
  content: string
  status: 'active' | 'superseded'
  supersedes: string | null
  created_at: string
  updated_at: string
}

export interface MemoryEvent {
  memory_id: string | null
  action: string
  detail: string | null
  created_at: string
}
