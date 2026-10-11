// /records and /records/:entity — the decisions, readable by anyone (DESIGN.md §13.5): what was
// forecast, what was advised, what the school or colony did, what the station measured, what it
// protected. Plain sentences; names, not ids.
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getEntityRecords, getRecordsIndex } from '@/lib/api'
import { RECORD_STEPS, type EntityRecords, type RecordsIndex } from '@/lib/protocol'
import { useStore } from '@/lib/store'
import DecisionList, { useEntityName } from '@/components/Records/DecisionList'
import ImpactStrip from '@/components/Public/ImpactStrip'

export default function Records() {
  const { entity } = useParams()
  const { manifest, load } = useStore()
  const nameOf = useEntityName()
  const [ent, setEnt] = useState<EntityRecords | null>(null)
  const [idx, setIdx] = useState<RecordsIndex | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  useEffect(() => {
    setErr(null); setEnt(null); setIdx(null)
    if (entity) getEntityRecords(entity).then(setEnt).catch((e) => setErr((e as Error).message))
    else getRecordsIndex().then(setIdx).catch((e) => setErr((e as Error).message))
  }, [entity])
  const records = entity ? ent?.records ?? [] : idx?.records ?? []
  const present = RECORD_STEPS.filter((s) => records.some((r) => r.kind === s.kind))
  return (
    <div className="min-h-full bg-ink px-4 py-5 text-fg">
      <div className="mx-auto max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Decisions</div>
        <h1 className="text-xl font-semibold">{entity ? nameOf(entity) : idx?.date ? `Today · ${idx.date}` : 'Today'}</h1>
        <p className="mt-1 text-[13px] leading-relaxed text-mute">What the model said, what was advised, what the school or colony did, what the nearest station then measured, and what that protected. One record per step, no contact details, open to anyone. Impact is credited only for the days the station confirmed.</p>
        {!entity && <ImpactStrip date={idx?.date} />}
        {present.length > 0 && <div className="mt-3 font-mono text-[10.5px] uppercase tracking-wider text-mute">steps on record: {present.map((s) => s.label).join(' · ')}</div>}
        {err && <div className="mt-3 font-mono text-xs text-red-300">{err}</div>}
        {!err && !ent && !idx && <div className="mt-4 h-40 animate-pulse rounded-xl bg-panel" />}
        {(ent || idx) && <div className="mt-4"><DecisionList records={records} groupByEntity={!entity} /></div>}
      </div>
    </div>
  )
}
