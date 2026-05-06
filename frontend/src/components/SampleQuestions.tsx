interface Props {
  samples: string[]
  onSelect: (q: string) => void
  disabled: boolean
}

export function SampleQuestions({ samples, onSelect, disabled }: Props) {
  if (!samples.length) return null

  return (
    <div className="flex flex-wrap justify-center gap-2 px-4 pb-2">
      {samples.map(q => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          disabled={disabled}
          className="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-600
                     shadow-sm transition hover:bg-brand-50 hover:border-brand-400
                     disabled:cursor-not-allowed disabled:opacity-40"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
