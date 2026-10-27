// Thin typed client for the Python REST API. Every per-user call goes through
// /api/users/{userId}/..., mirroring how the backend scopes data per user.

import type {
  DemoUser, Memory, MemoryEvent, MemoryKind, Message, Session, Status, TurnResult,
} from './types'

/** Error carrying the backend's `detail` message so the UI can show it. */
export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const user = (userId: string) => `/users/${encodeURIComponent(userId)}`

export const api = {
  status: () => request<Status>('/status'),
  users: () => request<DemoUser[]>('/users'),

  // Conversations
  sessions: (u: string) => request<Session[]>(`${user(u)}/sessions`),
  createSession: (u: string) => request<Session>(`${user(u)}/sessions`, { method: 'POST' }),
  deleteSession: (u: string, sid: string) =>
    request<void>(`${user(u)}/sessions/${sid}`, { method: 'DELETE' }),
  messages: (u: string, sid: string) => request<Message[]>(`${user(u)}/sessions/${sid}/messages`),
  ask: (u: string, sid: string, text: string) =>
    request<TurnResult>(`${user(u)}/sessions/${sid}/messages`, {
      method: 'POST', body: JSON.stringify({ text }),
    }),

  // Memory inspector
  memories: (u: string, includeSuperseded = false) =>
    request<Memory[]>(`${user(u)}/memories?include_superseded=${includeSuperseded}`),
  addMemory: (u: string, kind: MemoryKind, content: string) =>
    request<Memory>(`${user(u)}/memories`, { method: 'POST', body: JSON.stringify({ kind, content }) }),
  correctMemory: (u: string, id: string, content: string) =>
    request<Memory>(`${user(u)}/memories/${id}`, { method: 'PATCH', body: JSON.stringify({ content }) }),
  forgetMemory: (u: string, id: string) =>
    request<void>(`${user(u)}/memories/${id}`, { method: 'DELETE' }),
  forgetAll: (u: string) => request<{ deleted: number }>(`${user(u)}/memories`, { method: 'DELETE' }),
  memoryEvents: (u: string) => request<MemoryEvent[]>(`${user(u)}/memory-events`),
}
