// "What this choice does": for the actions chosen right now, the share of the hours at risk they
// cover, the people-hours protected and exposed, three sentences from the model, and the one
// action to add. Re-asks the API as the choice changes (debounced); the arithmetic is the server's.
import { useEffect, useRef, useState } from 'react'
import { postAssess, type Assessment } from '@/lib/api'

export default function AssessmentBox({ entityId, runId, actions, headers, onAdd, colour = '#ffb347' }: { entityId: string; runId: string; actions: string[]; headers: Record<string, string>; onAdd?: (id: string) => void; colour?: string }) {
  const [a, setA] = useState<Assessment | null>(null)
  const [busy, setBusy] = useState(false)
  const key = actions.slice().sort().join(',')
  const seq = useRef(0)
  useEffect(() => {
    const mine = ++seq.current
    setBusy(true)
    const t = window.setTimeout(() => {
      postAssess(entityId, { runId, actions }, headers).then((r) => { if (mine === seq.current) setA(r) }).catch(() => { if (mine === seq.current) setA(null) }).finally(() => { if (mine === seq.current) setBusy(false) })
    }, 450)
    return () => window.clearTimeout(t)
  }, [entityId, runId, key, headers.Authorization])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!a && !busy) return null
  const pct = Math.round((a?.coverage ?? 0) * 100)
  return (
    <div className="rounded-lg border border-line bg-ink p-3" aria-live="polite" data-assessment={pct}>
      <div className="flex items-baseline justify-between"><div className="font-mono text-[10px] uppercase tracking-[0.2em] text-mute">What this choice does</div>{busy && <span className="font-mono text-[10px] text-mute">updating…</span>}</div>
      {a && (
        <>
          <div className="mt-2 flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: colour }} /></div>
            <div className="w-12 text-right font-mono text-[12px] text-fg">{pct}%</div>
          </div>
          <div className="mt-1 font-mono text-[10.5px] text-mute">
            {a.kind === 'source'
              ? `${a.cellsActioned} of ${a.cellsAtRisk} high-risk cells actioned`
              : `${a.protectedHours} of ${a.hoursAtRisk} hours at risk covered · ${a.people.toLocaleString('en-IN')} people · ${a.value.toLocaleString('en-IN')} ${a.unit}${(a.exposedHours ?? 0) > 0 ? ` · ${a.exposedHours} h still exposed` : ''}`}
          </div>
          <p className="mt-2 text-[12.5px] leading-relaxed text-fg/90">{a.narrative.en}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[9.5px] uppercase tracking-wider text-mute">{a.narrative.source === 'agent' ? 'assessed automatically' : 'standard assessment'}</span>
            {a.missing.slice(0, 2).map((m) => (
              onAdd ? <button key={m.id} type="button" onClick={() => onAdd(m.id)} className="hairline h-6 rounded-full px-2 font-mono text-[10px] text-fg/80 hover:bg-white/5">+ {m.label.toLowerCase()} · {Math.round(m.weight * 100)}%</button>
                    : <span key={m.id} className="hairline h-6 rounded-full px-2 font-mono text-[10px] leading-6 text-mute">missing: {m.label.toLowerCase()} · {Math.round(m.weight * 100)}%</span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
