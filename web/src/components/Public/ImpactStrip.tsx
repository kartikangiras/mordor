// Today, in the open: what the decisions protected (from /api/impact; zero when nothing was
// logged, never a made-up number). On the validation page and above the decisions.
import { useEffect, useState } from 'react'
import { getImpact, type ImpactReport } from '@/lib/api'

const fmt = (n: number | undefined | null) => (n === undefined || n === null ? '—' : n.toLocaleString('en-IN'))

export default function ImpactStrip({ date }: { date?: string } = {}) {
  const [r, setR] = useState<ImpactReport | null>(null)
  useEffect(() => { getImpact(date).then(setR).catch(() => setR(null)) }, [date])
  if (!r) return null
  const tiles: [string, string, string][] = [
    [fmt(r.studentsProtected ?? r.students), 'students protected', 'schools that acted on their card'],
    [fmt(r.peopleProtected ?? r.people), 'people covered', 'students, residents and beds on cards that acted'],
    [fmt(r.outdoorHoursAvoided), 'outdoor hours avoided', 'window hours at Very Poor or worse'],
    [r.plan ? `${fmt(r.plan.areaKm2)} km²` : '—', 'under the action plan', r.plan ? `${r.plan.cells} burn-risk cells · ${r.plan.offices} office${r.plan.offices === 1 ? '' : 's'}${r.plan.radiusKm ? ` · ${r.plan.radiusKm} km radius` : ''}` : 'no plan today'],
    [fmt(r.hospitalsAlerted), 'hospitals on alert', r.bedsReady ? `${fmt(r.bedsReady)} beds kept ready` : 'wards alerted today'],
    [fmt(r.decisionsLogged), 'decisions logged', `${r.records.verified} verified · ${r.records.provisional} provisional`],
  ]
  return (
    <section className="my-4">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-mute">Today · {r.date}</div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map(([v, k, sub]) => (
          <div key={k} className="glass glass-tight p-3">
            <div className="text-xl font-semibold tracking-tight text-fg">{v}</div>
            <div className="text-[12px] text-fg/80">{k}</div>
            <div className="font-mono text-[10px] leading-snug text-mute">{sub}</div>
          </div>
        ))}
      </div>
      <div className="mt-1 font-mono text-[10px] text-mute">Impact is credited only for the days the nearest station confirmed; the rest stays provisional.</div>
    </section>
  )
}
