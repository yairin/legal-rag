import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevDisabled = useRef(disabled)

  useEffect(() => {
    if (prevDisabled.current && !disabled) {
      textareaRef.current?.focus()
    }
    prevDisabled.current = disabled
  }, [disabled])

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

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm
                 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100
                 transition-shadow"
    >
      <textarea
        ref={textareaRef}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        rows={1}
        placeholder="שאל שאלה משפטית…"
        disabled={disabled}
        className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed
                   placeholder:text-slate-400 focus:outline-none disabled:opacity-50"
        dir="rtl"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        aria-label="שלח"
        className="shrink-0 rounded-xl bg-brand-500 p-2.5 text-white shadow
                   transition-all hover:bg-brand-600 active:scale-95
                   disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100"
      >
        {disabled ? (
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
              d="M12 19l-7-7 7-7m8 7H5" />
          </svg>
        )}
      </button>
    </form>
  )
}
