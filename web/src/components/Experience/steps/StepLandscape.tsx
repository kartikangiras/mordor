import { useState } from 'react'
import { AREAS, type Area } from '@/config/areas'
import { useStore } from '@/lib/store'
import { haversineKm } from '@/lib/grid'
import { PhaseButton, Fact } from '../Phase'
import type { AreaData } from './common'

export default function StepLandscape({ area, d, onArea, onComplete, colour }: { area: Area; d: AreaData; onArea: (a: Area) => void; onComplete: () => void; colour: string }) {
  const { setLayers, fires, manifest } = useStore()
  const [phase, setPhase] = useState(1)
  const a = d.inArea
  const hottest = () => {
    if (!fires) return area
    const counts = AREAS.map((x) => ({ x, n: fires.features.filter((f) => haversineKm(x.lat, x.lon, f.geometry.coordinates[1], f.geometry.coordinates[0]) <= x.radiusKm).length }))
    return counts.sort((p, q) => q.n - p.n)[0]?.x ?? area
  }
  return (
    <div className="space-y-2">
      <PhaseButton active={phase === 1} done={phase > 1} colour={colour} onClick={() => { setLayers(['fires']); setPhase(2) }}>Load tonight's fire detections</PhaseButton>
      {phase > 1 && a && (
        <div>
          <Fact k="VIIRS detections, 24 h, whole domain" v={fires?.features.length ?? '—'} />
          <Fact k="within this area" v={`${a.fires.length} · ${a.frpMw.toFixed(0)} MW`} />
        </div>
      )}
      <PhaseButton active={phase === 2} done={phase > 2} colour={colour} onClick={() => { setLayers(['fires', 'ndvi']); setPhase(3) }}>Load the vegetation (NDVI)</PhaseButton>
      {phase > 2 && a && (
        <div>
          <Fact k="composite" v={manifest?.ndvi?.date ?? '—'} />
          <Fact k="NDVI change, last 16 days" v={a.ndviMean === null ? '—' : `${a.ndviMean.toFixed(3)} · ${a.ndviMean < -0.05 ? 'harvested or burned' : 'standing crop'}`} />
          <Fact k="these dates in 2024" v={a.climMean === null ? '—' : `${a.climMean.toFixed(1)} fires / cell / day`} />
        </div>
      )}
      {phase >= 3 && (
        <div className="space-y-1 pt-1">
          <div className="font-mono text-[11px] text-mute">Pick the area that matters today</div>
          <div className="flex gap-1">
            <select value={area.id} onChange={(e) => onArea(AREAS.find((x) => x.id === e.target.value)!)} className="h-10 flex-1 rounded border border-line bg-ink px-2 font-mono text-[11px] text-fg">
              {AREAS.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
            <button type="button" onClick={() => onArea(hottest())} className="h-10 rounded border border-line px-2 font-mono text-[11px] text-fg hover:border-fire">where it burns most</button>
          </div>
        </div>
      )}
      <PhaseButton active={phase === 3} done={phase > 3} colour={colour} onClick={() => { setLayers(['fires', 'ndvi', 'burnrisk']); setPhase(4) }}>Score the burning risk per cell</PhaseButton>
      {phase > 3 && a && (
        <div>
          <Fact k="cells burning now / scored" v={`${a.burningNow} / ${a.cells.length}`} />
          {a.cells.slice(0, 3).map((c) => <Fact key={`${c.i}-${c.j}`} k={c.name} v={`${c.score} ${c.category}`} />)}
          <div className="pt-1 font-mono text-[10px] text-mute">Click a cell on the map for its score breakdown.</div>
        </div>
      )}
      <PhaseButton active={phase === 4} colour={colour} onClick={onComplete}>Hand over to Anita →</PhaseButton>
    </div>
  )
}
