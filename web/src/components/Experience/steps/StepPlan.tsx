import { useState } from 'react'
import type { Area } from '@/config/areas'
import { useStore } from '@/lib/store'
import { postPlan } from '@/lib/api'
import { BURN_CATS, TIERS, type TierId } from '@/lib/aqi'
import { istLabel } from '@/lib/time'
import ExposureChart from '@/components/Detail/ExposureChart'
import { PhaseButton, Fact, Done } from '../Phase'
import { pickActor, type AreaData } from './common'

export default function StepPlan({ area, d, headers, onComplete, colour }: { area: Area; d: AreaData; headers: Record<string, string>; onComplete: () => void; colour: string }) {
  const { entities, setLayers, manifest } = useStore()
  const actor = pickActor(d, entities, area, { kind: 'source' })
  const [phase, setPhase] = useState(1)
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const cells = (d.inArea?.cells ?? []).slice(0, 6)
  const hours = (d.inArea?.actors ?? []).filter((x) => x.kind === 'exposure')
  const arrival = d.series.find((p) => (p.fire ?? 0) >= 30)
  const peak = d.series.length ? Math.max(...d.series.map((p) => p.total ?? p.bg)) : null
  const submit = async () => {
    if (!actor || !manifest) return
    setBusy(true); setErr(null)
    try {
      const r = await postPlan(actor.id, { runId: manifest.runId, cells: cells.filter((c) => picked[`${c.i}-${c.j}`]), hoursToProtect: hours.map((h) => ({ id: h.id, name: h.name, tier: h.dayTier, headline: h.headline })),
        actions: ['dispatch_balers', 'nodal_visits'], weather: d.windNow ? { windMs: Math.round(d.windNow.speed * 10) / 10, fromDeg: Math.round(d.windNow.from), rain48mm: d.inArea?.rain48 } : null }, headers)
      setDone(r.record.seq); setPhase(5)
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2">
      <PhaseButton active={phase === 1} done={phase > 1} colour={colour} onClick={() => { setLayers(['plume', 'burnrisk', 'actors']); setPhase(2) }}>Run the predictive model for the area</PhaseButton>
      {phase > 1 && (
        <div>
          {d.series.length && manifest ? <ExposureChart series={d.series} currentHour={d.hour} calibrated={manifest.calibration.k !== null} /> : <div className="h-40 animate-pulse rounded bg-ink/60" />}
          <Fact k="peak total PM2.5, 48 h" v={peak === null ? '—' : `${peak.toFixed(0)} µg/m³`} />
          <Fact k="plume arrives" v={arrival ? (arrival.hour === 0 ? 'already here' : `+${arrival.hour} h · ${istLabel(arrival.t)} IST`) : 'not within 48 h'} />
        </div>
      )}
      <PhaseButton active={phase === 2} done={phase > 2} colour={colour} onClick={() => setPhase(3)}>Check the weather window</PhaseButton>
      {phase > 2 && (
        <div className="rounded border border-line bg-ink px-2 py-1.5 font-mono text-[11px] text-mute">
          wind {d.windNow ? `${d.windNow.speed.toFixed(1)} m/s from ${d.windNow.from.toFixed(0)}°` : '—'} · rain 48 h {d.inArea?.rain48 ?? '—'} mm · {d.inArea && (d.inArea.rain48 ?? 0) >= 5 ? <span className="text-[#7fb069]">rain suppresses burning</span> : <span className="text-fire">dry: burning likely to continue</span>}
        </div>
      )}
      <PhaseButton active={phase === 3} done={phase > 3} colour={colour} onClick={() => setPhase(4)}>Mark the treatment cells</PhaseButton>
      {phase > 3 && (
        <div className="space-y-1">
          {cells.length === 0 && <div className="font-mono text-[11px] text-mute">no burn-risk cells in this area; the plan covers the hours to protect</div>}
          {cells.map((c) => { const cat = BURN_CATS.find((x) => x.label === c.category) ?? BURN_CATS[0]; const k = `${c.i}-${c.j}`; return (
            <label key={k} className="flex min-h-10 items-center gap-2 rounded border border-line px-2 font-mono text-[11px] text-fg">
              <input type="checkbox" className="h-4 w-4 accent-[#F59E0B]" checked={!!picked[k]} disabled={!!done} onChange={() => setPicked((x) => ({ ...x, [k]: !x[k] }))} />
              <span className="flex-1">{c.name} <span className="text-mute">{c.km.toFixed(0)} km · {c.fires24} fires/24 h</span></span>
              <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: cat.colour }}>{c.score} {c.category}</span>
            </label>) })}
          {hours.length > 0 && <div className="pt-1 font-mono text-[11px] text-mute">Hours to protect</div>}
          {hours.map((h) => <Fact key={h.id} k={h.name} v={h.dayTier && h.dayTier in TIERS ? <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: TIERS[h.dayTier as TierId].colour }}>{h.dayTier} {TIERS[h.dayTier as TierId].label}</span> : '—'} />)}
          <PhaseButton active={phase === 4} done={phase > 4} busy={busy} colour={colour} onClick={submit}>Submit the plan{actor ? ` as ${actor.persona ?? actor.personTitle}` : ''}</PhaseButton>
        </div>
      )}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
      {done !== null && <Done>Plan logged · record #{done} · {Object.values(picked).filter(Boolean).length} cells, {hours.length} entities' hours</Done>}
      <PhaseButton active={phase === 5} colour={colour} onClick={onComplete}>Hand over to Rekha →</PhaseButton>
    </div>
  )
}
