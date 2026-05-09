import { useCallback, useEffect, useState } from 'react'
import { streamChat } from '../lib/api'
import type { Message } from '../lib/types'

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


  // Safety net: if loading gets stuck for >3 minutes, force-unlock
  useEffect(() => {
    if (!loading) return
    const id = setTimeout(() => {
      setLoading(false)
      setStatus('')
    }, 180_000)
    return () => clearTimeout(id)
  }, [loading])

  const clearMessages = useCallback(() => {
    setMessages([])
    setStatus('')
  }, [])

  const sendMessage = useCallback(async (question: string) => {
    if (loading) return

    const history = messages
      .filter(m => !m.isStreaming && m.text)
      .slice(-10)
      .map(m => ({ role: m.role, text: m.text }))

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
      for await (const event of streamChat(question, history)) {
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
          const elapsed = Date.now() - startTime
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, sources: event.sources, isStreaming: false, elapsedMs: elapsed }
                : m
            )
          )
          setLoading(false)
          setStatus('')
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
  }, [loading, messages])

  return { messages, loading, status, sendMessage, clearMessages }
}
