import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChat } from '../lib/api'
import type { Message } from '../lib/types'


let _idCounter = 0
const uid = () => String(++_idCounter)

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)


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

    const abort = new AbortController()
    abortRef.current = abort

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setLoading(true)
    setStatus('מתחיל עיבוד...')
    const startTime = Date.now()

    try {
      for await (const event of streamChat(question, history, abort.signal)) {
        if (event.type === 'status') {
          setStatus(event.message)
        } else if (event.type === 'delta') {
          setStatus('')
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, text: m.text + event.text } : m
            )
          )
        } else if (event.type === 'replace') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, text: event.text } : m
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
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, text: 'אירעה שגיאה בחיבור לשרת.', isStreaming: false }
              : m
          )
        )
      }
    } finally {
      abortRef.current = null
      setLoading(false)
      setStatus('')
    }
  }, [loading, messages])

  const stopMessage = useCallback(() => {
    if (!abortRef.current) return
    abortRef.current.abort()
    setMessages(prev => {
      const streaming = prev.find(m => m.isStreaming)
      if (!streaming) return prev
      return prev.map(m =>
        m.isStreaming
          ? { ...m, isStreaming: false, text: m.text + '\n\n_המענה הופסק באמצע._' }
          : m
      )
    })
    setLoading(false)
    setStatus('')
  }, [])

  return { messages, loading, status, sendMessage, stopMessage, clearMessages }
}
