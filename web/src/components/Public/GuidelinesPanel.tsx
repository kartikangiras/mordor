// "What to do today" for a chosen exposure zone (PIVOT_PLAN.md §5): the zone's worst tier in
// the next 48 h, when the smoke arrives and peaks, four plain rows, the GRAP anchor, and the
// one line that points people with a role to their own screen.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { TIERS, type TierId } from '@/lib/aqi'
import { istLabel } from '@/lib/time'

export default function GuidelinesPanel({ compact = false, zoneId }: { compact?: boolean; zoneId?: string }) {
  const zones = useStore((s) => s.zones)
  const guidelines = useStore((s) => s.guidelines)
  const [pick, setPick] = useState<string | null>(null)
  if (!zones || !zones.zones.length) return <div className="text-[11px] text-mute">No zones in this run.</div>
  if (!guidelines) return <div className="text-[11px] text-mute">Guidance is loading…</div>
  const id = pick ?? zoneId ?? zones.rankingPeak[0]
  const z = zones.zones.find((x) => x.id === id) ?? zones.zones[0]
  const tier = (z.worstTier in TIERS ? z.worstTier : 'T0') as TierId
  const g = guidelines[tier]
  return (
    <div className={compact ? 'text-[12px]' : 'text-[13px]'}>
      <div className="flex items-center justify-between gap-2">
        <select value={z.id} onChange={(e) => setPick(e.target.value)} aria-label="Zone" className="hairline h-8 min-w-0 max-w-[62%] truncate rounded-lg bg-ink/60 px-2 text-[12px] text-fg">
          {zones.rankingPeak.map((zid) => { const zz = zones.zones.find((x) => x.id === zid); return zz ? <option key={zid} value={zid}>{zz.name}</option> : null })}
        </select>
        <span className="shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold text-ink" style={{ background: TIERS[tier].colour }}>{TIERS[tier].label}</span>
      </div>
      <div className="mt-2 font-mono text-[10px] uppercase tracking-wider text-mute">
        {z.arrivalHour === null ? 'smoke not expected in 48 h' : z.arrivalHour === 0 ? 'smoke already here' : `smoke arrives in ${z.arrivalHour} h`}{z.peak?.t ? ` · worst ${istLabel(z.peak.t)} IST` : ''}
      </div>
      <div className="mt-2 text-[14px] font-semibold text-fg">{g.title}</div>
      {tier !== 'T0' && (
        <dl className="mt-2 space-y-1.5">
          {([['Outdoors', g.outdoor], ['Windows', g.windows], ['Masks', g.masks], ['At risk', g.vulnerable]] as const).map(([k, v]) => (
            <div key={k} className="flex gap-2"><dt className="w-16 shrink-0 font-mono text-[10px] uppercase tracking-wider text-mute">{k}</dt><dd className="text-fg/90">{v}</dd></div>
          ))}
        </dl>
      )}
      {g.grapAnchor && <div className="mt-2 font-mono text-[10px] text-mute">{g.grapAnchor}</div>}
      {g.advisory && <div className="mt-2 rounded-lg bg-fire/10 px-3 py-2 text-[12px] text-fg/90">{g.advisory}</div>}
      <div className="mt-3 border-t border-white/8 pt-2 text-[11px] text-mute">Run a school, an RWA or a district office? <Link to="/act" className="text-fg underline">For people who act →</Link></div>
    </div>
  )
}
