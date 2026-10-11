import { useState } from 'react'
import type { Area } from '@/config/areas'
import { useStore } from '@/lib/store'
import { fmtMetric } from '@/lib/aqi'
import { PhaseButton, Fact } from '../Phase'
import ObserveForm from '@/components/Act/ObserveForm'
import { pickActor, type AreaData } from './common'

export default function StepProof({ area, d, headers, onComplete, colour }: { area: Area; d: AreaData; headers: Record<string, string>; onComplete: () => void; colour: string }) {
  const { entities, manifest } = useStore()
  const actor = pickActor(d, entities, area, { type: 'rwa', kind: 'exposure' })
  const [done, setDone] = useState(false)
  if (!actor) return <div className="font-mono text-[11px] text-mute">Nothing to check.</div>
  return (
    <div className="space-y-2">
      <div className="text-base font-semibold text-fg">{actor.name}</div>
      <ObserveForm entityId={actor.id} date={actor.date ?? undefined} cardSaid={actor.dayTier ? `${actor.dayTier} · peak AQI ${actor.peakAqi ?? '—'} · ${actor.date}` : '—'} headers={headers} colour={colour} onDone={() => setDone(true)} />
      <div className="pt-1 font-mono text-[11px] text-mute">The model against last season</div>
      <Fact k="hindcast" v={manifest?.calibration.window ?? '—'} />
      <Fact k="R² / MAE" v={`${fmtMetric(manifest?.calibration.r2 ?? null)} / ${fmtMetric(manifest?.calibration.mae ?? null, 0)} µg/m³ · ${manifest?.calibration.stations ?? '—'} stations`} />
      <PhaseButton active={done} colour={colour} onClick={onComplete}>Hand over to Ms. Rao →</PhaseButton>
    </div>
  )
}
