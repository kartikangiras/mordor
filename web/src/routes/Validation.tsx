// /validation — the hindcast report in one screen (PIVOT_PLAN.md task 46): the verdict first,
// in a sentence computed from the numbers, then the numbers, the named right and wrong days, the
// scatter, one episode chart with a station picker, and the per-station table behind one control.
import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { getValidation, type Metrics, type ValidationReport } from '@/lib/api'
import { fmtK, fmtMetric } from '@/lib/aqi'
import Footer from '@/components/Footer'
import ImpactStrip from '@/components/Public/ImpactStrip'
import PageBackdrop from '@/components/PageBackdrop'

const pct = (v: number | null | undefined) => (v === null || v === undefined ? null : Math.round(v * 100))

function Row({ label, m }: { label: string; m: Metrics }) {
  return (
    <tr className="border-t border-white/8"><td className="py-1.5 pr-3 text-fg">{label}</td><td className="text-right">{fmtMetric(m.r2)}</td><td className="text-right">{fmtMetric(m.mae, 0)}</td><td className="text-right">{fmtMetric(m.bias, 0)}</td><td className="text-right">{fmtMetric(m.corr)}</td><td className="text-right">{m.n.toLocaleString('en-IN')}</td></tr>
  )
}

/** The report's verdict, in words the numbers support. */
function verdict(r: ValidationReport): string {
  const t = r.metrics.test, hr = r.metrics.hitRate
  const better = t.model.mae !== null && t.camsOnly.mae !== null ? t.camsOnly.mae - t.model.mae : null
  const a = `Out of sample over ${r.testDays} days and ${r.stations} stations, the model's error was ${fmtMetric(t.model.mae, 0)} µg/m³ against ${fmtMetric(t.camsOnly.mae, 0)} for the CAMS background alone`
  const b = better === null ? '' : better > 0 ? `, ${Math.round(better)} µg/m³ better` : better < 0 ? `, ${Math.round(-better)} µg/m³ worse` : ', no better'
  const c = hr.informative === false ? '. Every test day was Very Poor or worse, so the hit rate carries no skill information.' : `. It called ${pct(hr.pod) ?? '—'}% of the Very Poor-or-worse days a day ahead, with a ${pct(hr.far) ?? '—'}% false-alarm rate.`
  return a + b + c
}

export default function Validation() {
  const [r, setR] = useState<ValidationReport | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [station, setStation] = useState<number | null>(null)
  const [allStations, setAllStations] = useState(false)
  const [sortBy, setSortBy] = useState<'distance' | 'mae'>('distance')
  useEffect(() => { getValidation().then(setR).catch((e) => setErr((e as Error).message)) }, [])
  const stations = useMemo(() => (r ? [...r.perStation].sort((a, b) => a.distanceToDelhiKm - b.distanceToDelhiKm) : []), [r])
  const episodes = useMemo(() => (r ? [...r.episodes].sort((a, b) => (stations.findIndex((s) => s.id === a.id)) - (stations.findIndex((s) => s.id === b.id))) : []), [r, stations])
  const current = episodes.find((e) => e.id === station) ?? episodes.find((e) => r?.narrative.right.startsWith(e.name)) ?? episodes[0] ?? null
  if (err) return <div className="p-6 font-mono text-xs text-red-300">No hindcast report: {err}</div>
  if (!r) return <div className="p-6 font-mono text-xs text-mute">loading report…</div>
  const t = r.metrics.test
  const hr = r.metrics.hitRate
  const maxV = Math.max(...r.scatter.map(([a, b]) => Math.max(a, b)), 100)
  const table = [...stations].sort((a, b) => (sortBy === 'mae' ? (b.mae ?? 0) - (a.mae ?? 0) : a.distanceToDelhiKm - b.distanceToDelhiKm))
  return (
    <div className="relative min-h-full text-fg">
      <PageBackdrop image="clear" position="50% 40%" />
      <div className="relative mx-auto max-w-3xl px-4 py-6 font-mono text-xs text-mute">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Validation</div>
        <h1 className="font-sans text-2xl font-semibold tracking-tight text-fg">How well did this model do?</h1>
        <p className="mt-2 max-w-2xl font-sans text-[15px] leading-relaxed text-fg/90" data-verdict>{verdict(r)}</p>
        <p className="mt-1 max-w-2xl font-sans text-[12px] leading-relaxed text-mute">Hindcast {r.window}: run every day at 00 UTC with a 48 h horizon; k fitted on the first {r.fitDays} days, every number from the following {r.testDays}. {r.stationsDelhi} of the stations are within 40 km of Delhi. Fires {r.fires}; winds {r.windLevel}.</p>

        <ImpactStrip />

        <div className="glass glass-tight p-4">
          <table className="w-full">
            <thead><tr className="text-left text-[10px] uppercase tracking-wider"><th></th><th className="text-right">R²</th><th className="text-right">MAE µg/m³</th><th className="text-right">bias</th><th className="text-right">corr</th><th className="text-right">n</th></tr></thead>
            <tbody>
              <Row label="model: k·raw + CAMS" m={t.model} />
              <Row label="CAMS background only" m={t.camsOnly} />
              <Row label="lead 1–24 h" m={r.metrics.byLead.lead01_24.model} />
              <Row label="lead 25–48 h" m={r.metrics.byLead.lead25_48.model} />
            </tbody>
          </table>
          <div className="mt-3 text-[11px]">increment skill, corr(raw, obs − CAMS) <span className="text-fg">{fmtMetric(t.incrementCorr ?? null)}</span> · k {fmtK(r.k)}{r.kAnomaly !== undefined ? ` · anomaly-fit k ${fmtK(r.kAnomaly)}` : ''}</div>
          <div className="mt-1 text-[11px]">Very Poor+ called 24 h ahead: {hr.hits} hits, {hr.misses} misses, {hr.falseAlarms} false alarms, {hr.correctNegatives} correct negatives</div>
          <div className="mt-1 text-[11px]">peak timing error {r.metrics.peakTiming.meanAbsHours ?? '—'} h mean over {r.metrics.peakTiming.events} events</div>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="glass glass-tight p-4"><div className="mb-1 text-[10px] uppercase tracking-wider text-emerald-300">one it got right</div><div className="font-sans text-[13px] leading-relaxed text-fg/90">{r.narrative.right}</div></div>
          <div className="glass glass-tight p-4"><div className="mb-1 text-[10px] uppercase tracking-wider text-[#ff8a75]">one it got wrong</div><div className="font-sans text-[13px] leading-relaxed text-fg/90">{r.narrative.wrong}</div></div>
        </div>

        <div className="glass glass-tight mt-3 p-4">
          <div className="mb-1 text-fg">predicted vs observed PM2.5, µg/m³ · test days</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: -10 }}>
                <CartesianGrid stroke="#262c34" />
                <XAxis type="number" dataKey="x" name="predicted" domain={[0, maxV]} tick={{ fill: '#8b95a3', fontSize: 10 }} />
                <YAxis type="number" dataKey="y" name="observed" domain={[0, maxV]} tick={{ fill: '#8b95a3', fontSize: 10 }} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: maxV, y: maxV }]} stroke="#8b95a3" strokeDasharray="4 4" />
                <Tooltip contentStyle={{ background: '#14181d', border: '1px solid #262c34', fontSize: 11 }} />
                <Scatter data={r.scatter.map(([x, y]) => ({ x, y }))} fill="#d75b4a" fillOpacity={0.45} isAnimationActive={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {current && (
          <div className="glass glass-tight mt-3 p-4" data-episode>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-fg">one station, lead 1–24 h, stitched</div>
              <select aria-label="Station" value={current.id} onChange={(e) => setStation(Number(e.target.value))} className="h-9 max-w-full rounded border border-white/10 bg-ink px-2 text-[11px] text-fg">
                {episodes.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div className="mt-2 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={current.t.map((tt, i) => ({ t: tt.slice(5, 13).replace('T', ' '), obs: current.obs[i], pred: current.pred[i], bg: current.bg[i] }))} margin={{ top: 4, right: 8, bottom: 0, left: -14 }}>
                  <XAxis dataKey="t" tick={{ fill: '#8b95a3', fontSize: 9 }} interval={47} />
                  <YAxis tick={{ fill: '#8b95a3', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#14181d', border: '1px solid #262c34', fontSize: 11 }} />
                  <Line dataKey="obs" name="observed" stroke="#e8ebef" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                  <Line dataKey="pred" name="model" stroke="#d75b4a" dot={false} isAnimationActive={false} />
                  <Line dataKey="bg" name="CAMS" stroke="#8b95a3" dot={false} strokeDasharray="3 3" isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-1 text-[10px]">white observed · red model · dashed CAMS background</div>
          </div>
        )}

        <div className="glass glass-tight mt-3 p-4" data-stations>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <button type="button" onClick={() => setAllStations(!allStations)} aria-expanded={allStations} className="text-fg underline hover:text-fire">{allStations ? 'hide the stations' : `all ${r.stations} stations`}</button>
            {allStations && (
              <div className="flex gap-1 text-[10px]">
                {(['distance', 'mae'] as const).map((s) => <button key={s} type="button" onClick={() => setSortBy(s)} className={`h-7 rounded-full px-2.5 ${sortBy === s ? 'bg-white/10 text-fg' : 'text-mute hover:text-fg'}`}>{s === 'distance' ? 'nearest Delhi first' : 'worst error first'}</button>)}
              </div>
            )}
          </div>
          {allStations && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[520px]">
                <thead><tr className="text-left text-[10px] uppercase tracking-wider"><th>station</th><th className="text-right">km to Delhi</th><th className="text-right">R²</th><th className="text-right">MAE</th><th className="text-right">bias</th><th className="text-right">CAMS-only MAE</th></tr></thead>
                <tbody>{table.map((s) => (
                  <tr key={s.id} className="border-t border-white/8"><td className="py-1 text-fg">{s.name}</td><td className="text-right">{s.distanceToDelhiKm}</td><td className="text-right">{fmtMetric(s.r2)}</td><td className="text-right">{fmtMetric(s.mae, 0)}</td><td className="text-right">{fmtMetric(s.bias, 0)}</td><td className="text-right">{fmtMetric(s.camsOnlyMae, 0)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>

        <p className="mt-4 font-sans text-[12px] leading-relaxed">{r.disclaimer}</p>
        <Footer label="hindcast" runId={r.experimentId} calibration={{ k: r.k, r2: r.r2, mae: r.mae, window: r.window, stations: r.stations }} />
      </div>
    </div>
  )
}
