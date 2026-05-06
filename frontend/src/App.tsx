import { useEffect, useRef, useState } from 'react'
import { ChatInput } from './components/ChatInput'
import { MessageBubble } from './components/MessageBubble'
import { SampleQuestions } from './components/SampleQuestions'
import { useChat } from './hooks/useChat'
import { fetchSamples } from './lib/api'

export default function App() {
  const { messages, loading, status, sendMessage, clearMessages } = useChat()
  const [samples, setSamples] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchSamples().then(setSamples)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, status])

  const isEmpty = messages.length === 0
  const streamingId = messages.find(m => m.isStreaming)?.id

  return (
    <div className="flex h-dvh flex-col bg-gradient-to-b from-slate-50 to-white" dir="rtl">
      {/* Header */}
      <header className="shrink-0 border-b border-slate-200 bg-white/80 backdrop-blur-sm px-4 py-3 shadow-sm z-10">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 text-white shadow-md">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
            </svg>
          </div>
          <div className="flex-1">
            <h1 className="text-base font-semibold text-slate-900">עוזר משפטי — המרכז לשלטון מקומי</h1>
            <p className="text-xs text-slate-400">דיני עבודה ברשויות מקומיות מגובה מקורות</p>
          </div>
          {!isEmpty && (
            <button
              onClick={clearMessages}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5
                         text-xs text-slate-500 hover:bg-slate-50 hover:text-slate-700
                         transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title="שיחה חדשה"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 4v16m8-8H4" />
              </svg>
              שיחה חדשה
            </button>
          )}
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="mx-auto max-w-2xl px-4 py-6">
          {isEmpty ? (
            <WelcomeScreen />
          ) : (
            <div className="space-y-5">
              {messages.map(m => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  status={m.id === streamingId ? status : undefined}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input area */}
      <footer className="shrink-0 border-t border-slate-200 bg-white/90 backdrop-blur-sm pb-safe">
        <div className="mx-auto max-w-2xl px-4 pt-3 pb-3 space-y-2">
          {isEmpty && samples.length > 0 && (
            <SampleQuestions
              samples={samples}
              onSelect={sendMessage}
              disabled={loading}
            />
          )}
          <ChatInput onSend={sendMessage} disabled={loading} />
          <p className="text-center text-[11px] text-slate-400">
            המידע מבוסס על מסמכי המרכז לשלטון מקומי ואינו תחליף לייעוץ משפטי.
          </p>
        </div>
      </footer>
    </div>
  )
}

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-50 shadow-inner">
        <svg className="h-10 w-10 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
        </svg>
      </div>
      <h2 className="mb-2 text-2xl font-semibold text-slate-800">שלום! אני העוזר המשפטי שלך</h2>
      <p className="max-w-sm text-sm text-slate-500 leading-relaxed">
        שאל כל שאלה בנושאי דיני עבודה ברשויות המקומיות —
        זכויות עובדים, שכר, חופשות, פיטורים ועוד.
        <br className="mt-1" />
        כל תשובה מגובה בציטוט מדויק ממסמכי המרכז לשלטון מקומי.
      </p>
    </div>
  )
}
