// Step 2, the principal: pick a school in the area (any of the mapped schools), register it,
// read tomorrow's card for it, log the actions. Nothing here is fixed to the demo school.
import { useEffect, useMemo, useState } from 'react'
import { useStore } from '@/lib/store'
import { getMyForecast, postAck, postRegister } from '@/lib/api'
import type { Card } from '@/lib/protocol'
import { TIERS, type TierId } from '@/lib/aqi'
import { ACTION_LABELS } from '@/lib/labels'
import { haversineKm } from '@/lib/grid'
import { PhaseButton, Fact, Done } from '../Phase'
import type { StepProps } from './common'
import AssessmentBox from '@/components/Act/AssessmentBox'

const rank = (t: string | null) => (t && t in TIERS ? ['T0', 'T1', 'T2', 'T3', 'T4'].indexOf(t) : -1)

export default function StepCommunity({ area, d, headers, onComplete, colour, school, onSchool }: StepProps) {
  const schools = useStore((s) => s.schools)
  const [phase, setPhase] = useState(1)
  const [busy, setBusy] = useState(false)
  const [rec, setRec] = useState<{ seq: number; existing: boolean } | null>(null)
  const [card, setCard] = useState<Card | null>(null)
  const [actions, setActions] = useState<string[]>([])
  const toggle = (id: string) => setActions((x) => (x.includes(id) ? x.filter((y) => y !== id) : [...x, id]))
  const [acked, setAcked] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)

  // candidates: the area's mapped schools, worst tier first, then nearest; the nearest mapped ones when the area has none
  const { options, nearestOnly } = useMemo(() => {
    const all = (schools?.features ?? []).map((f) => ({ f, km: haversineKm(area.lat, area.lon, f.geometry.coordinates[1], f.geometry.coordinates[0]) }))
    const inArea = all.filter((x) => x.km <= area.radiusKm)
    const pool = inArea.length ? inArea : all
    const sorted = pool.sort((a, b) => rank(b.f.properties.dayTier) - rank(a.f.properties.dayTier) || (b.f.properties.peakAqi ?? 0) - (a.f.properties.peakAqi ?? 0) || a.km - b.km).slice(0, 15)
    return { options: sorted, nearestOnly: inArea.length === 0 }
  }, [schools, area])
  useEffect(() => {
    if (!school && options[0]) { const f = options[0].f; onSchool?.({ id: f.properties.id, name: f.properties.name, name_hi: f.properties.name_hi, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] }) }
  }, [options, school, onSchool])
  const chosen = school ? options.find((o) => o.f.properties.id === school.id)?.f ?? schools?.features.find((f) => f.properties.id === school.id) ?? null : null
  if (!schools) return <div className="h-40 animate-pulse rounded bg-ink/60" />
  if (!options.length) return <div className="font-mono text-[11px] text-mute">No mapped schools in this run.</div>
  const p = chosen?.properties
  const tier = p?.dayTier && p.dayTier in TIERS ? TIERS[p.dayTier as TierId] : null
  const km = school ? haversineKm(area.lat, area.lon, school.lat, school.lon) : null

  const register = async () => {
    if (!school) return
    setBusy(true); setErr(null)
    try { const r = await postRegister({ entityId: school.id }, headers); setRec({ seq: r.record.seq, existing: r.existing }); setPhase(3) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const preview = async () => {
    if (!school) return
    setBusy(true); setErr(null)
    try { const c = await getMyForecast(headers, school.id); setCard(c); setActions(c.acked?.actions ?? c.defaultActions); setPhase(4) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const logActions = async () => {
    if (!school || !card) return
    setBusy(true); setErr(null)
    try { const r = await postAck(school.id, { runId: card.runId, actions, sentVia: 'noted' }, headers); setAcked(r.record?.seq ?? 0); setPhase(5) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const cardTier = card?.dayTier && card.dayTier in TIERS ? TIERS[card.dayTier as TierId] : null
  return (
    <div className="space-y-2">
      <div className="font-mono text-[11px] text-mute">{nearestOnly ? `No mapped schools inside ${area.name}; the nearest ones` : `${options.length} of the schools in ${area.name}, worst tomorrow first`}</div>
      <select value={school?.id ?? ''} disabled={phase > 1} onChange={(e) => { const o = options.find((x) => x.f.properties.id === e.target.value); if (o) onSchool?.({ id: o.f.properties.id, name: o.f.properties.name, name_hi: o.f.properties.name_hi, lat: o.f.geometry.coordinates[1], lon: o.f.geometry.coordinates[0] }) }} aria-label="School" className="h-10 w-full rounded border border-line bg-ink px-2 font-mono text-[11px] text-fg disabled:opacity-70">
        {options.map((o) => <option key={o.f.properties.id} value={o.f.properties.id}>{o.f.properties.name}{o.f.properties.dayTier ? ` · ${TIERS[o.f.properties.dayTier as TierId]?.label ?? o.f.properties.dayTier}` : ''} · {o.km.toFixed(0)} km</option>)}
      </select>
      {school && (
        <>
          <div className="text-base font-semibold text-fg">{school.name} {school.name_hi && <span className="font-normal text-mute">{school.name_hi}</span>}</div>
          <div className="flex gap-6 border-b border-line pb-3 pt-1">
            <div><div className="font-mono text-[10px] uppercase text-mute">tomorrow</div><div className="text-xl font-light" style={{ color: tier?.colour ?? '#8b95a3' }}>{tier?.label ?? '—'}</div></div>
            <div><div className="font-mono text-[10px] uppercase text-mute">peak AQI</div><div className="text-xl font-light text-fg">{p?.peakAqi ?? '—'}</div></div>
            <div><div className="font-mono text-[10px] uppercase text-mute">from the centre</div><div className="text-xl font-light text-fg">{km === null ? '—' : `${km.toFixed(0)} km`}</div></div>
          </div>
          <Fact k="hours of concern" v={`${schools.schoolHoursIst.join('–')} · dismissal ${schools.dismissalIst.join('–')} IST`} />
          <Fact k="peak hour" v={p?.peakHourIst ? `${p.peakHourIst} IST` : '—'} />
          <Fact k="students" v="not on record" />
          <Fact k="fires within the area" v={d.inArea?.fires.length ?? 0} />
        </>
      )}
      <PhaseButton active={phase === 1 && !!school} done={phase > 1} colour={colour} onClick={() => setPhase(2)}>Confirm the details</PhaseButton>
      <PhaseButton active={phase === 2} done={phase > 2} busy={busy && phase === 2} colour={colour} onClick={register}>Register the school</PhaseButton>
      {rec && <Done>Registration {rec.existing ? 'already on record' : 'written'} · record #{rec.seq} · awaiting Dr. Mehta's approval</Done>}
      <PhaseButton active={phase === 3} done={phase > 3} busy={busy && phase === 3} colour={colour} onClick={preview}>Read tomorrow's card</PhaseButton>
      {card && (
        <div className="rounded px-3 py-2 text-ink" style={{ background: cardTier?.colour ?? '#6b7480' }}>
          <div className="text-[11px] opacity-80">{card.date}</div>
          <div className="text-lg font-bold leading-tight">{cardTier?.label ?? 'No advice yet'}</div>
          <div className="text-[12px]">{card.headline}</div>
        </div>
      )}
      {card && (card.actions ?? []).map((a) => (
        <label key={a.id} className="flex min-h-10 items-center gap-2 rounded border border-line px-2 font-mono text-[11px] text-fg">
          <input type="checkbox" className="h-4 w-4 accent-[#FB923C]" checked={actions.includes(a.id)} disabled={phase > 4} onChange={() => toggle(a.id)} />
          <span>{a.label}</span>
        </label>
      ))}
      {card && school && <AssessmentBox entityId={school.id} runId={card.runId} actions={actions} headers={headers} onAdd={phase > 4 ? undefined : toggle} colour={colour} />}
      {card && card.message && <div className="rounded border border-line bg-ink p-2 text-[12px] leading-relaxed text-fg">{card.message.hi}<div className="mt-1 text-[11px] text-fg/80">{card.message.en}</div></div>}
      <PhaseButton active={phase === 4} done={phase > 4} busy={busy && phase === 4} colour={colour} onClick={logActions}>Log tomorrow's actions</PhaseButton>
      {acked !== null && <Done>Logged for {school?.name} · {actions.map((a) => ACTION_LABELS[a] ?? a).join(', ') || 'no actions'} · record #{acked}</Done>}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
      <PhaseButton active={phase >= 3} colour={colour} onClick={onComplete}>Hand over to Dr. Mehta →</PhaseButton>
    </div>
  )
}
