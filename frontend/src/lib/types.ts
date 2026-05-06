export interface SourceCard {
  source_id: string
  quote: string
  title: string
  url?: string
  filename?: string
  page?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  sources?: SourceCard[]
  isStreaming?: boolean
  elapsedMs?: number
}

export type SSEEvent =
  | { type: 'delta'; text: string }
  | { type: 'replace'; text: string }
  | { type: 'sources'; sources: SourceCard[] }
  | { type: 'status'; message: string }
  | { type: 'done' }
  | { type: 'error'; message: string }
