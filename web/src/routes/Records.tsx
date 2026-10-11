// /records — the decisions of the day, one card per entity: what was forecast, what was advised,
// what the person did, what the station said, what it protected (PIVOT_PLAN.md task 44). Five
// lines each, the latest of its kind, a count instead of a repeat. /records/:entity is the history.
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getEntityRecords, getImpact, getRecordsIndex, type ImpactReport } from '@/lib/api'
import type { EntityRecords, RecordsIndex } from '@/lib/protocol'
import { useStore } from '@/lib/store'
import { demoMode } from '@/lib/auth'
import { DEMO_NOTE } from '@/lib/experience'
import { istLabel } from '@/lib/time'
import { dayStates, TYPE_LABELS } from '@/lib/records'
import DecisionList, { useEntityName } from '@/components/Records/DecisionList'
import EntityCard from '@/components/Records/EntityCard'
import PageBackdrop from '@/components/PageBackdrop'

export default function Records() {
  const { entity } = useParams()
  const { manifest, load } = useStore()
  const nameOf = useEntityName()
  const [ent, setEnt] = useState<EntityRecords | null>(null)
  const [idx, setIdx] = useState<RecordsIndex | null>(null)
  const [impact, setImpact] = useState<ImpactReport | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  useEffect(() => {
    setErr(null); setEnt(null); setIdx(null)
    if (entity) getEntityRecords(entity).then(setEnt).catch((e) => setErr((e as Error).message))
    else { getRecordsIndex().then(setIdx).catch((e) => setErr((e as Error).message)); getImpact().then(setImpact).catch(() => setImpact(null)) }
  }, [entity])
  const states = idx ? dayStates(idx.records) : []
  const day = idx?.date ? istLabel(`${idx.date}T06:30:00Z`).replace(/,.*$/, '') : null
  return (
    <div className="relative min-h-full text-fg">
      <PageBackdrop image="night" position="52% 50%" />
      <div className="relative mx-auto max-w-4xl px-4 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Decisions</div>
        {entity ? (
          <>
            <h1 className="text-2xl font-semibold tracking-tight">{nameOf(entity)}</h1>
            <p className="mt-1 text-[13px] leading-relaxed text-mute">Every record for this {TYPE_LABELS[ent?.records[0]?.actorType ?? ''] ?? 'entity'}, newest first. <Link to="/records" className="underline hover:text-fg">All of today's decisions</Link></p>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-semibold tracking-tight">{day ? `Today · ${day}` : 'Today'}</h1>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-mute">What the model forecast, what was advised, what each school, colony, office or hospital did, what the nearest station then measured, and what that protected. Open to anyone; no contact details.</p>
            {impact && (
              <div className="mt-3 flex flex-wrap items-baseline gap-x-5 gap-y-1 font-mono text-[12px] text-mute" data-impact-line>
                <span><span className="text-lg font-semibold text-fg">{impact.decisionsLogged}</span> decisions today</span>
                <span><span className="text-lg font-semibold text-fg">{impact.records.verified}</span> verified</span>
                <span><span className="text-lg font-semibold text-fg">{impact.records.provisional}</span> provisional</span>
                <Link to="/validation" className="underline hover:text-fg">what it protected →</Link>
              </div>
            )}
            {demoMode && <p className="mt-2 max-w-2xl font-mono text-[10.5px] leading-relaxed text-mute" data-demo-note>{DEMO_NOTE}</p>}
          </>
        )}
        {err && <div className="mt-3 font-mono text-xs text-red-300">{err}</div>}
        {!err && !ent && !idx && <div className="mt-4 h-40 animate-pulse rounded-xl bg-white/5" />}
        {idx && !entity && (states.length ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">{states.map((s) => <EntityCard key={s.entity} s={s} name={nameOf(s.entity)} />)}</div>
        ) : <div className="mt-4 font-mono text-[11px] text-mute">No decisions yet today.</div>)}
        {ent && entity && <div className="glass glass-tight mt-4 p-4"><DecisionList records={ent.records} /></div>}
      </div>
    </div>
  )
}
