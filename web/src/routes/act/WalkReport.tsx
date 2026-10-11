// /act/walk/report — the report of the last action plan: the area and school it ran for, what
// the day's decisions protected, and the day of every entity the eight steps touched, in the
// same five lines as the decisions page. From here a visitor starts another plan for another
// area, or goes to the map. Demo builds only; the walk's choices live in this browser session,
// the records on the server.
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { getRecordsIndex } from '@/lib/api'
import type { RecordsIndex } from '@/lib/protocol'
import { demoMode } from '@/lib/auth'
import { EXP_STEPS, PERSONAS, readProgress, readWalk, writeProgress, writeWalk } from '@/lib/experience'
import { dayStates } from '@/lib/records'
import { istLabel } from '@/lib/time'
import { useStore } from '@/lib/store'
import { useEntityName } from '@/components/Records/DecisionList'
import EntityCard from '@/components/Records/EntityCard'
import ImpactStrip from '@/components/Public/ImpactStrip'
import PageBackdrop from '@/components/PageBackdrop'

const DEMO_ENTITIES = ['rwa-demo-rohini', 'dao-demo-sangrur', 'hosp-demo-rohini']

export default function WalkReport() {
  const navigate = useNavigate()
  const { manifest, load } = useStore()
  const nameOf = useEntityName()
  const [idx, setIdx] = useState<RecordsIndex | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  useEffect(() => { getRecordsIndex().then(setIdx).catch((e) => setErr((e as Error).message)) }, [])
  if (!demoMode) return <Navigate to="/act" replace />
  const walk = readWalk()
  const done = readProgress()
  const steps = EXP_STEPS.filter((_, i) => done[i]).length
  const firstOpen = EXP_STEPS.findIndex((_, i) => !done[i])
  const touched = [walk.school?.id, ...DEMO_ENTITIES].filter((x): x is string => !!x)
  const states = idx ? dayStates(idx.records).filter((s) => touched.includes(s.entity)) : []
  const people = [...new Set(EXP_STEPS.map((s) => s.persona))].map((n) => PERSONAS[n])
  const restart = () => { writeProgress({}); writeWalk({ school: null, area: null }); navigate('/act/walk/1') }
  const day = idx?.date ? istLabel(`${idx.date}T06:30:00Z`).replace(/,.*$/, '') : null
  return (
    <div className="relative min-h-full text-fg">
      <PageBackdrop image="night" position="52% 50%" />
      <div className="relative mx-auto max-w-4xl px-4 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Action plan · report</div>
        <h1 className="text-2xl font-semibold tracking-tight">{steps === EXP_STEPS.length ? 'Your last action plan' : `Your action plan so far · ${steps} of ${EXP_STEPS.length} steps`}</h1>
        <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-mute" data-walk-summary>
          {walk.area ? `${walk.area.name} · ` : ''}{walk.school ? `${walk.school.name} · ` : 'no school chosen yet · '}{day ?? 'today'}. {people.length} people took the eight steps; every decision below is on the public record.
          {steps < EXP_STEPS.length && firstOpen >= 0 && <> <Link to={`/act/walk/${firstOpen + 1}`} className="underline hover:text-fg">Continue at step {firstOpen + 1}</Link>.</>}
        </p>
        <div className="mt-4 flex flex-wrap gap-2" data-walk-report-actions>
          <button type="button" onClick={restart} className="flex h-11 items-center gap-3 rounded-full bg-fire px-6 text-[13px] font-semibold text-ink transition hover:bg-[#ffc46a]">Start another action plan <span className="h-2 w-2 animate-pulse rounded-full bg-[#d7263d]" /></button>
          <Link to="/map" className="hairline flex h-11 items-center rounded-full px-5 text-[13px] font-medium text-fg hover:bg-white/5">Explore the map</Link>
          <Link to="/records" className="flex h-11 items-center px-2 font-mono text-[11px] text-mute underline hover:text-fg">All of today's decisions</Link>
        </div>
        <ImpactStrip date={idx?.date} />
        {err && <div className="mt-3 font-mono text-xs text-red-300">{err}</div>}
        {!err && !idx && <div className="mt-4 h-40 animate-pulse rounded-xl bg-white/5" />}
        {idx && (states.length
          ? <div className="mt-2 grid gap-3 md:grid-cols-2">{states.map((s) => <EntityCard key={s.entity} s={s} name={nameOf(s.entity)} />)}</div>
          : <div className="mt-4 font-mono text-[11px] text-mute">No decisions on record for this plan yet.</div>)}
      </div>
    </div>
  )
}
