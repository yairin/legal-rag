import { useCallback, useRef, useState } from 'react'
import { streamChat } from '../lib/api'
import type { Message, SourceCard } from '../lib/types'

function stripCiteTags(text: string): string {
  return text
    .replace(/<cite\s+source="[^"]*">/g, '')
    .replace(/<\/cite>/g, '')
}

let _idCounter = 0
const uid = () => String(++_idCounter)

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)

  const clearMessages = useCallback(() => {
    setMessages([])
    setStatus('')
  }, [])

  const sendMessage = useCallback(async (question: string) => {
    if (loading) return

    const userMsg: Message = { id: uid(), role: 'user', text: question }
    const assistantId = uid()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      text: '',
      isStreaming: true,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setLoading(true)
    setStatus('מתחיל עיבוד...')
    const startTime = Date.now()

    try {
      for await (const event of streamChat(question)) {
        if (event.type === 'status') {
          setStatus(event.message)
        } else if (event.type === 'delta') {
          setStatus('')
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, text: m.text + stripCiteTags(event.text) } : m
            )
          )
        } else if (event.type === 'replace') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, text: stripCiteTags(event.text) } : m
            )
          )
        } else if (event.type === 'sources') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, sources: event.sources, isStreaming: false }
                : m
            )
          )
        } else if (event.type === 'done') {
          const elapsed = Date.now() - startTime
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, isStreaming: false, elapsedMs: elapsed } : m
            )
          )
        } else if (event.type === 'error') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, text: event.message, isStreaming: false }
                : m
            )
          )
        }
      }
    } catch {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, text: 'אירעה שגיאה בחיבור לשרת.', isStreaming: false }
            : m
        )
      )
    } finally {
      setLoading(false)
      setStatus('')
    }
  }, [loading])

  return { messages, loading, status, sendMessage, clearMessages }
}
