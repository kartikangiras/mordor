// Chapter "What happens after the forecast": one entity's decisions, step by step.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getEntityRecords } from '@/lib/api'
import { RECORD_STEPS, type EntityRecords } from '@/lib/protocol'
import { sentence, who, useEntityName } from '@/components/Records/DecisionList'
import { istLabel } from '@/lib/time'

export default function RecordsPanel({ entity }: { entity: string }) {
  const [log, setLog] = useState<EntityRecords | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { getEntityRecords(entity).then(setLog).catch((e) => setErr((e as Error).message)) }, [entity])
  const byKind = new Map((log?.records ?? []).map((r) => [r.kind, r]))
  const nameOf = useEntityName()
  return (
    <div className="glass absolute bottom-24 right-4 top-20 w-[min(420px,calc(100%-2rem))] overflow-y-auto p-4 font-mono text-[11px] text-mute max-sm:inset-x-2 max-sm:top-60">
      <div className="font-sans text-sm font-semibold text-fg">Decisions · {nameOf(entity)}</div>
      <div className="mb-2 text-[10px]">{log ? `${log.records.length} records · contact-free · readable by anyone` : err ?? 'loading…'}</div>
      <ol className="space-y-1.5">
        {RECORD_STEPS.map((s, i) => {
          const r = byKind.get(s.kind)
          return (
            <li key={s.kind} className={`rounded border px-2 py-1.5 ${r ? 'border-fire/60 text-fg' : 'border-line'}`}>
              <div className="flex items-center justify-between"><span>{i + 1}. {s.label} <span className="text-mute">· {s.who}</span></span>{r && <span className="text-[10px] text-mute">{istLabel(r.ts)}</span>}</div>
              <div className="text-[10px] text-mute">{r ? `${who(r)} ${sentence(r)}` : s.kind === 'verify' ? 'waiting for the station data (archive lags ~4 days)' : 'pending'}</div>
            </li>
          )
        })}
      </ol>
      <div className="mt-2 text-[10px]"><Link to={`/records/${encodeURIComponent(entity)}`} className="underline">all decisions</Link> · impact is credited only when the nearest station confirmed the day</div>
    </div>
  )
}
