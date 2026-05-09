import { useState } from 'react'
import type { SourceCard as SourceCardType } from '../lib/types'

interface Props {
  source: SourceCardType
}

function cleanTitle(title: string | undefined, url: string): string {
  if (title && title !== url && title.length < 80) return title
  try {
    const u = new URL(url)
    const slug = u.pathname.split('/').filter(Boolean).pop() ?? ''
    const readable = decodeURIComponent(slug).replace(/[-_]/g, ' ')
    return readable || u.hostname.replace('www.', '')
  } catch {
    return 'קישור'
  }
}

export function SourceCard({ source }: Props) {
  const [expanded, setExpanded] = useState(false)

  const label = source.url
    ? cleanTitle(source.title, source.url)
    : source.title

  const hasLongQuote = source.quote && source.quote.length > 120

  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 overflow-hidden text-sm">
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="shrink-0 text-brand-400">
          {source.url ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          )}
        </span>

        <div className="flex-1 min-w-0">
          {source.url ? (
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-brand-600 hover:underline truncate block"
            >
              {label}
            </a>
          ) : (
            <span className="font-medium text-slate-700 truncate block">{label}</span>
          )}
        </div>

        {source.quote && (
          <button
            onClick={() => setExpanded(v => !v)}
            className="shrink-0 text-slate-400 hover:text-slate-600 transition-colors"
            aria-label={expanded ? 'הסתר ציטוט' : 'הצג ציטוט'}
          >
            <svg
              className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}
      </div>

      {source.quote && (expanded || !hasLongQuote) && (
        <div className="border-t border-slate-100 px-3 py-2">
          <blockquote className="border-r-2 border-brand-300 pr-3 text-slate-600 italic text-xs leading-relaxed">
            {source.quote}
          </blockquote>
        </div>
      )}
    </div>
  )
}
