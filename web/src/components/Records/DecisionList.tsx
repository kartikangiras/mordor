// The history of one entity's decisions (PIVOT_PLAN.md task 44): one row per decision, newest
// first, the pipeline's eight-a-day rows folded to the latest with a count, a person's repeated
// identical records folded to one with "logged N times". Names, not ids; a sentence, not a payload;
// the labelled details behind one control.
import { useState } from 'react'
import { useStore } from '@/lib/store'
import { RECORD_STEPS, type DecisionRecord } from '@/lib/protocol'
import { istLabel } from '@/lib/time'
import { actionsText, foldHistory, sentence, spanLabel, tierLabel, who } from '@/lib/records'
import { OUTCOME_LABELS } from '@/lib/labels'

export { sentence, who }

/** id -> display name, from the people and schools layers in the store. */
export function useEntityName(): (id: string) => string {
  const entities = useStore((s) => s.entities)
  const schools = useStore((s) => s.schools)
  return (id) => entities?.features.find((f) => f.properties.id === id)?.properties.name ?? schools?.features.find((f) => f.properties.id === id)?.properties.name ?? id
}

const DETAIL_KEYS: [string, string, (v: unknown) => string][] = [
  ['date', 'day', String], ['dayTier', 'tier', (v) => tierLabel(v) ?? String(v)], ['peakAqi', 'peak AQI', String], ['actions', 'actions', actionsText], ['sentVia', 'sent via', (v) => (v === 'noted' || v === 'copy' ? 'recorded without sending' : String(v))],
  ['outcome', 'outcome', (v) => OUTCOME_LABELS[String(v)] ?? String(v).replace(/_/g, ' ')], ['evidence', 'evidence', String], ['reason', 'reason', String], ['status', 'status', (v) => String(v).replace(/_/g, ' ')],
  ['value', 'value', String], ['unit', 'unit', String], ['people', 'people', String], ['hours', 'hours', (v) => (Array.isArray(v) ? v.join('–') : String(v))], ['dismissal', 'dismissal', (v) => (Array.isArray(v) ? v.join('–') : String(v))],
  ['cells', 'cells', (v) => (Array.isArray(v) ? v.map((c) => (c as { name?: string }).name ?? '').filter(Boolean).join(', ') : String(v))], ['outdoorHoursCancelled', 'outdoor hours cancelled', String], ['chars', 'message length', (v) => `${v} characters`],
]

function Row({ r, times, first, runs }: { r: DecisionRecord; times: number; first: string; runs: number }) {
  const [open, setOpen] = useState(false)
  const step = RECORD_STEPS.find((s) => s.kind === r.kind)
  const details = DETAIL_KEYS.filter(([k]) => r.payload[k] !== undefined && r.payload[k] !== null && r.payload[k] !== '').map(([k, label, fmt]) => [label, fmt(r.payload[k])] as const)
  return (
    <li className="border-t border-white/8 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="text-[13px] leading-relaxed text-fg"><span className="mr-2 rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-fg/80">{step?.label ?? r.kind}</span><span className="text-mute">{who(r)}</span> {sentence(r)}</div>
        <div className="font-mono text-[10.5px] text-mute">
          {times > 1 ? <>logged {times} times, {spanLabel(first, r.ts)} IST</> : <>{istLabel(r.ts)} IST</>}
          {runs > 1 && <> · {runs} runs today</>}
        </div>
      </div>
      {details.length > 0 && (
        <div className="mt-1">
          <button type="button" onClick={() => setOpen(!open)} className="font-mono text-[10.5px] text-mute underline hover:text-fg">{open ? 'less' : 'details'}</button>
          {open && <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-[12px]">{details.map(([k, v]) => <div key={k} className="contents"><dt className="font-mono text-[10.5px] uppercase tracking-wider text-mute">{k}</dt><dd className="text-fg/90">{v}</dd></div>)}</dl>}
        </div>
      )}
    </li>
  )
}

/** The folded history, newest first. */
export default function DecisionList({ records }: { records: DecisionRecord[] }) {
  if (!records.length) return <div className="font-mono text-[11px] text-mute">No decisions yet.</div>
  return <ol>{foldHistory(records).map(({ r, times, first, runs }) => <Row key={r.id} r={r} times={times} first={first} runs={runs} />)}</ol>
}
