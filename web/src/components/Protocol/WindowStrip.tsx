// 08:00 -> 16:00 bar segmented by hour and coloured by tier; label always accompanies colour.
import { TIERS } from '@/lib/aqi'
import type { Window } from '@/lib/protocol'


function mins(s: string): number { const [h, m] = s.split(':').map(Number); return h * 60 + m }

export default function WindowStrip({ windows, schoolHours, dismissal, strip }: { windows: Window[]; schoolHours?: [string, string]; dismissal?: [string, string]; strip?: [string, string] }) {
  const START = strip ? mins(strip[0]) : 8 * 60, END = strip ? mins(strip[1]) : 16 * 60
  const span = END - START
  const marks: number[] = []
  for (let h = Math.ceil(START / 60); h <= END / 60; h += Math.max(1, Math.round((END - START) / 60 / 4))) marks.push(h)
  return (
    <div>
      <div className="relative h-8 w-full overflow-hidden rounded border border-line bg-ink">
        {windows.map((w) => {
          const a = Math.max(START, mins(w.fromIst)), b = Math.min(END, mins(w.toIst))
          if (b <= a) return null
          return (
            <div key={w.fromIst} className="absolute top-0 flex h-full items-center justify-center overflow-hidden text-[10px] font-semibold text-ink"
              style={{ left: `${((a - START) / span) * 100}%`, width: `${((b - a) / span) * 100}%`, background: TIERS[w.tier].colour }}
              title={`${w.fromIst}–${w.toIst} ${w.tier} ${TIERS[w.tier].label}${w.peakAqi ? ` · AQI ${w.peakAqi}` : ''}`}>
              {b - a >= 120 ? `${w.tier} ${TIERS[w.tier].label}` : w.tier}
            </div>
          )
        })}
        {schoolHours && (
          <div className="pointer-events-none absolute bottom-0 h-1 bg-fg/70" style={{ left: `${((mins(schoolHours[0]) - START) / span) * 100}%`, width: `${((mins(schoolHours[1]) - mins(schoolHours[0])) / span) * 100}%` }} />
        )}
        {dismissal && (
          <div className="pointer-events-none absolute bottom-0 h-1 bg-fg/70" style={{ left: `${((mins(dismissal[0]) - START) / span) * 100}%`, width: `${((mins(dismissal[1]) - mins(dismissal[0])) / span) * 100}%` }} />
        )}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-mute">
        {marks.map((h) => <span key={h}>{h >= 24 ? '12 am' : h > 12 ? `${h - 12} pm` : h === 12 ? '12 pm' : `${h} am`}</span>)}
      </div>
      <div className="font-mono text-[10px] text-mute">underline = school hours and dismissal · one segment per hour, coloured and labelled by tier</div>
    </div>
  )
}
