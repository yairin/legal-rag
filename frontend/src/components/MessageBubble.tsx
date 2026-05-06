import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useEffect, useRef, useState } from 'react'
import { SourceCard } from './SourceCard'
import type { Message } from '../lib/types'

interface Props {
  message: Message
  status?: string
}

export function MessageBubble({ message, status }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-start items-end gap-2">
        <div className="shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-500">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
          </svg>
        </div>
        <div className="max-w-[78%] rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-3 text-slate-800 shadow-sm">
          <p className="leading-relaxed text-sm">{message.text}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-end items-end gap-2">
      <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-white px-4 py-3 shadow-md ring-1 ring-slate-100">
        {message.text ? (
          <div className="prose prose-slate max-w-none text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.text}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="inline-block h-4 w-0.5 animate-pulse bg-brand-400 align-text-bottom ms-0.5 rounded-full" />
            )}
          </div>
        ) : (
          message.isStreaming && <ThinkingIndicator status={status} />
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-4 space-y-2 border-t border-slate-100 pt-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">מקורות</p>
            {message.sources.map(s => (
              <SourceCard key={s.source_id} source={s} />
            ))}
          </div>
        )}

        <Timer isStreaming={!!message.isStreaming} elapsedMs={message.elapsedMs} />
      </div>

      <div className="shrink-0 w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center shadow-sm">
        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
        </svg>
      </div>
    </div>
  )
}

function Timer({ isStreaming, elapsedMs }: { isStreaming: boolean; elapsedMs?: number }) {
  const [ticks, setTicks] = useState(0)
  const startRef = useRef(Date.now())

  useEffect(() => {
    if (!isStreaming) return
    startRef.current = Date.now()
    setTicks(0)
    const id = setInterval(() => setTicks(Date.now() - startRef.current), 100)
    return () => clearInterval(id)
  }, [isStreaming])

  const ms = isStreaming ? ticks : elapsedMs
  if (ms === undefined) return null

  return (
    <p className="mt-2 text-[11px] text-slate-300 text-left tabular-nums">
      ⏱ {(ms / 1000).toFixed(1)}s
    </p>
  )
}

function ThinkingIndicator({ status }: { status?: string }) {
  return (
    <div className="flex items-center gap-3 py-1">
      <div className="flex gap-1">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-brand-300 animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
      {status && (
        <span className="text-xs text-slate-400 animate-pulse">{status}</span>
      )}
    </div>
  )
}
