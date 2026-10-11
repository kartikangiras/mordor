// The stacked split is the point (DESIGN.md §9.4): how much of tomorrow is the fires.
import { Area, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PM25_RAMP } from '@/lib/aqi'
import { istClock } from '@/lib/time'

export interface SeriesPoint { t: string; hour: number; bg: number; fire: number | null; total: number | null; istHour: number; inSchool: boolean }

export default function ExposureChart({ series, currentHour, calibrated }: { series: SeriesPoint[]; currentHour: number; calibrated: boolean }) {
  if (!series.length) return null
  const data = series.map((p) => ({ ...p, label: istClock(p.t) }))
  // school-hour bands as contiguous spans of hour indices
  const spans: { from: number; to: number }[] = []
  for (const p of data) {
    if (!p.inSchool) continue
    const last = spans[spans.length - 1]
    if (last && last.to === p.hour - 1) last.to = p.hour
    else spans.push({ from: p.hour, to: p.hour })
  }
  const ymax = Math.ceil((Math.max(60, ...data.map((p) => p.total ?? p.bg)) * 1.1) / 50) * 50
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
          {spans.map((s) => (
            <ReferenceArea key={`span-${s.from}`} x1={s.from} x2={s.to + 0.99} fill="#e8ebef" fillOpacity={0.06} ifOverflow="hidden" />
          ))}
          {PM25_RAMP.map((r) => (
            <ReferenceLine key={`band-${r.from}`} y={r.from} stroke={r.colour} strokeDasharray="2 4" strokeOpacity={0.7} />
          ))}
          <ReferenceLine x={currentHour} stroke="#ffb347" strokeWidth={1.5} />
          <XAxis dataKey="hour" type="number" domain={[0, data.length - 1]} tickCount={7}
            tickFormatter={(h: number) => data[h]?.label ?? ''} tick={{ fill: '#8b95a3', fontSize: 10 }} axisLine={{ stroke: '#262c34' }} tickLine={false} />
          <YAxis domain={[0, ymax]} tickFormatter={(v: number) => String(Math.round(v))} tick={{ fill: '#8b95a3', fontSize: 10 }} axisLine={false} tickLine={false} width={44} />
          <Tooltip
            contentStyle={{ background: '#14181d', border: '1px solid #262c34', fontFamily: 'ui-monospace, monospace', fontSize: 11 }}
            labelFormatter={(h) => `${data[Number(h)]?.label} IST · +${h} h`}
            formatter={(v, name) => [typeof v === 'number' ? `${v.toFixed(0)} µg/m³` : '—', name]}
          />
          <Area type="monotone" dataKey="bg" name="background (CAMS)" stackId="pm" stroke="#8b95a3" fill="#8b95a3" fillOpacity={0.35} isAnimationActive={false} />
          {calibrated && <Area type="monotone" dataKey="fire" name="stubble fire (ours)" stackId="pm" stroke="#d75b4a" fill="#d75b4a" fillOpacity={0.55} isAnimationActive={false} />}
          {calibrated && <Line type="monotone" dataKey="total" name="total" stroke="#e8ebef" dot={false} strokeWidth={1.5} isAnimationActive={false} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
