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
import { TIERS } from '@/lib/aqi'
import { istClock, istLabel } from '@/lib/time'
import { dayStates, TYPE_LABELS, type DayState } from '@/lib/records'
import DecisionList, { useEntityName } from '@/components/Records/DecisionList'
import PageBackdrop from '@/components/PageBackdrop'

function Line({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="contents">
      <dt className="pt-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-mute">{label}</dt>
      <dd className={`pt-1.5 text-[13px] leading-snug ${muted ? 'text-mute' : 'text-fg'}`}>{value}</dd>
    </div>
  )
}

function EntityCard({ s, name }: { s: DayState; name: string }) {
  const tier = s.tier ? TIERS[s.tier] : null
  return (
    <section className="glass glass-tight p-4" data-entity-card={s.entity}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <Link to={`/records/${encodeURIComponent(s.entity)}`} className="text-[15px] font-semibold text-fg hover:underline">{name}</Link>
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-mute">
          <span>{TYPE_LABELS[s.actorType] ?? s.actorType}</span>
          {tier && <span className="rounded px-1.5 py-0.5 font-semibold text-ink" style={{ background: tier.colour }}>{tier.label}</span>}
        </div>
      </div>
      <dl className="mt-2 grid grid-cols-[86px_1fr] gap-x-3 border-t border-white/8">
        <Line label="Forecast" value={s.forecast ? `${s.forecast.text} · run ${istClock(s.forecast.ts)}` : 'no card for today'} muted={!s.forecast} />
        {s.advised
          ? <Line label="Advised" value={s.advised.text} />
          : s.registered
            ? <Line label="Registered" value={`by ${s.registered.by}, ${istClock(s.registered.ts)}${s.registered.approved ? ' · approved' : ' · awaiting approval'}`} />
            : <Line label="Advised" value="no advisory yet" muted />}
        <Line label="Decided" value={s.decided ? `${s.decided.by} · ${s.decided.text} · ${istClock(s.decided.ts)}${s.decided.times > 1 ? ` · logged ${s.decided.times} times today` : ''}` : 'no decision yet'} muted={!s.decided} />
        <Line label="Checked" value={s.checked ? `${s.checked.text}${s.checked.by ? ` · ${s.checked.by}, ${istClock(s.checked.ts)}` : ''}` : 'pending — the station confirms the day tomorrow'} muted={!s.checked} />
        <Line label="Credited" value={s.credited ? s.credited.text : 'nothing credited yet'} muted={!s.credited} />
      </dl>
    </section>
  )
}

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
