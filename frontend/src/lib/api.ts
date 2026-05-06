import type { SSEEvent } from './types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function fetchSamples(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/api/samples`)
    if (!res.ok) return []
    const data = await res.json()
    return data.samples ?? []
  } catch {
    return []
  }
}

export async function* streamChat(
  question: string,
  turnstileToken?: string
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, turnstile_token: turnstileToken }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'שגיאת שרת' }))
    const detail = err.detail
    const message = typeof detail === 'string' ? detail : 'שגיאת שרת'
    yield { type: 'error', message }
    return
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      let finished = false
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: SSEEvent = JSON.parse(line.slice(6))
            yield event
            if (event.type === 'done' || event.type === 'error') {
              finished = true
              break
            }
          } catch {
            // ignore malformed lines
          }
        }
      }
      if (finished) break
    }
  } finally {
    reader.cancel()
  }
}
