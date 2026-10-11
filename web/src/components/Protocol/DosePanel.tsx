// A concentration is not a decision; an inhaled mass is. This panel says how much PM2.5 a
// child actually breathes across the hours the card covers, and which single hour to move.
// Basis and breathing rates are shown, never hidden: see services/protocol/interval.py.
import type { Dose, Interval } from '@/lib/protocol'

function fmtUg(ug: number): string {
  return ug >= 1000 ? `${(ug / 1000).toFixed(1)} mg` : `${Math.round(ug)} µg`
}

const ACTIVITY_LABEL: Record<string, string> = {
  rest: 'sitting',
  light: 'in class',
  moderate: 'outdoors, active',
}

export default function DosePanel({ dose, interval }: { dose?: Dose | null; interval?: Interval | null }) {
  if (!dose && !interval) return null
  const worstShare = dose?.worstHourShare != null ? Math.round(dose.worstHourShare * 100) : null
  return (
    <div className="space-y-2 rounded border border-line bg-ink p-3">
      {interval && (
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wide text-mute">worst hour</div>
          <div className="text-[15px] leading-snug text-fg">
            <span className="text-xl font-semibold">AQI {interval.aqi}</span>
            <span className="text-mute"> at {interval.hourIst}</span>
          </div>
          <div className="font-mono text-[11px] text-mute">
            likely between <span className="text-fg">{interval.aqiLo}</span> and{' '}
            <span className="text-fg">{interval.aqiHi}</span> · {interval.pm25Lo}–{interval.pm25Hi} µg/m³
          </div>
        </div>
      )}

      {dose && (
        <div className="border-t border-line pt-2">
          <div className="font-mono text-[10px] uppercase tracking-wide text-mute">
            breathed over {dose.hours} h of school and pick-up
          </div>
          <div className="text-[15px] leading-snug text-fg">
            <span className="text-xl font-semibold">{fmtUg(dose.totalUg)}</span>
            <span className="text-mute"> of PM2.5</span>
          </div>
          <div className="mt-1 space-y-0.5 font-mono text-[11px] text-mute">
            <div>
              in class {fmtUg(dose.schoolHoursUg)} · pick-up {fmtUg(dose.dismissalUg)}
              {dose.dismissalShare != null && (
                <span className="text-fg"> ({Math.round(dose.dismissalShare * 100)}% in one hour)</span>
              )}
            </div>
            <div>
              worst single hour <span className="text-fg">{dose.worstHour.hourIst}</span> ·{' '}
              {ACTIVITY_LABEL[dose.worstHour.activity] ?? dose.worstHour.activity} ·{' '}
              {fmtUg(dose.worstHour.ug)}
              {worstShare != null && <span> ({worstShare}% of the day)</span>}
              {' '}— <span className="text-fg">move this one first</span>
            </div>
          </div>
        </div>
      )}

      <div className="border-t border-line pt-2 font-mono text-[10px] leading-relaxed text-mute">
        {interval && <div>Range: {interval.basis}.</div>}
        {dose && (
          <div>
            Dose: {dose.basis}. Breathing rates m³/h —{' '}
            {Object.entries(dose.breathingRatesM3PerH).map(([k, v]) => `${k} ${v}`).join(', ')}.
          </div>
        )}
      </div>
    </div>
  )
}
