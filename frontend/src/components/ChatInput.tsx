import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'

interface Props {
  onSend: (text: string) => void
  onStop?: () => void
  disabled: boolean
}

// Minimal types for the Web Speech API (not fully covered by @types/typescript DOM)
type SR = new () => {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: { results: { [i: number]: { [j: number]: { transcript: string } } } }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

function getSpeechRecognition(): SR | null {
  if (typeof window === 'undefined') return null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition ?? null
}

export function ChatInput({ onSend, onStop, disabled }: Props) {
  const [text, setText] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevDisabled = useRef(disabled)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null)

  useEffect(() => {
    if (prevDisabled.current && !disabled) {
      textareaRef.current?.focus()
    }
    prevDisabled.current = disabled
  }, [disabled])

  useEffect(() => {
    if (disabled && isRecording) {
      recognitionRef.current?.stop()
    }
  }, [disabled, isRecording])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const toggleRecording = () => {
    if (isRecording) {
      recognitionRef.current?.stop()
      setIsRecording(false)
      return
    }

    const SR = getSpeechRecognition()
    if (!SR) {
      alert('הדפדפן שלך אינו תומך בהקלטה קולית. נסה Chrome או Edge.')
      return
    }

    const recognition = new SR()
    recognition.lang = 'he-IL'
    recognition.continuous = false
    recognition.interimResults = true

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (e: any) => {
      let transcript = ''
      for (let i = 0; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript
      }
      setText(transcript)
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
        textareaRef.current.style.height =
          `${Math.min(textareaRef.current.scrollHeight, 160)}px`
      }
    }

    recognition.onend = () => setIsRecording(false)
    recognition.onerror = () => setIsRecording(false)

    recognitionRef.current = recognition
    recognition.start()
    setIsRecording(true)
  }

  const hasSpeechAPI = getSpeechRecognition() !== null

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm
                 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100
                 transition-shadow"
    >
      {/* Mic button — right side in RTL layout */}
      {hasSpeechAPI && !disabled && (
        <button
          type="button"
          onClick={toggleRecording}
          aria-label={isRecording ? 'עצור הקלטה' : 'הקלט שאלה'}
          title={isRecording ? 'לחץ לעצירה' : 'הקלטה קולית'}
          className={`shrink-0 rounded-xl p-2.5 transition-all active:scale-95
            ${isRecording
              ? 'bg-red-500 text-white shadow animate-pulse'
              : 'text-slate-400 hover:text-brand-500 hover:bg-brand-50'
            }`}
        >
          {isRecording ? (
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
              <rect x="2"  y="9" width="2" height="6" rx="1"/>
              <rect x="6"  y="6" width="2" height="12" rx="1"/>
              <rect x="10" y="4" width="2" height="16" rx="1"/>
              <rect x="14" y="6" width="2" height="12" rx="1"/>
              <rect x="18" y="9" width="2" height="6" rx="1"/>
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23" strokeWidth={2} strokeLinecap="round"/>
              <line x1="8"  y1="23" x2="16" y2="23" strokeWidth={2} strokeLinecap="round"/>
            </svg>
          )}
        </button>
      )}

      <textarea
        ref={textareaRef}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        rows={1}
        placeholder={isRecording ? 'מקשיב…' : 'שאל שאלה משפטית…'}
        disabled={disabled}
        className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed
                   placeholder:text-slate-400 focus:outline-none disabled:opacity-50"
        dir="rtl"
      />

      {disabled && onStop ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="עצור"
          className="shrink-0 rounded-xl bg-red-500 p-2.5 text-white shadow
                     transition-all hover:bg-red-600 active:scale-95"
        >
          <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          aria-label="שלח"
          className="shrink-0 rounded-xl bg-brand-500 p-2.5 text-white shadow
                     transition-all hover:bg-brand-600 active:scale-95
                     disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
              d="M12 19l-7-7 7-7m8 7H5" />
          </svg>
        </button>
      )}
    </form>
  )
}
