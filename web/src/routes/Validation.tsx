// /validation — the hindcast report, including the named failure case (DESIGN.md §13.2).
import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { getValidation, type Metrics, type ValidationReport } from '@/lib/api'
import { fmtK, fmtMetric } from '@/lib/aqi'
import Footer from '@/components/Footer'
import ImpactStrip from '@/components/Public/ImpactStrip'

function Row({ label, m }: { label: string; m: Metrics }) {
  return (
    <tr className="border-t border-line"><td className="py-1 pr-3 text-fg">{label}</td><td className="text-right">{fmtMetric(m.r2)}</td><td className="text-right">{fmtMetric(m.mae, 0)}</td><td className="text-right">{fmtMetric(m.bias, 0)}</td><td className="text-right">{fmtMetric(m.corr)}</td><td className="text-right">{m.n}</td></tr>
  )
}

export default function Validation() {
  const [r, setR] = useState<ValidationReport | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { getValidation().then(setR).catch((e) => setErr((e as Error).message)) }, [])
  if (err) return <div className="p-6 font-mono text-xs text-red-300">No hindcast report: {err}</div>
  if (!r) return <div className="p-6 font-mono text-xs text-mute">loading report…</div>
  const t = r.metrics.test
  const hr = r.metrics.hitRate
  const maxV = Math.max(...r.scatter.map(([a, b]) => Math.max(a, b)), 100)
  return (
    <div className="min-h-full bg-ink px-4 py-4 text-fg">
      <div className="mx-auto max-w-3xl font-mono text-xs text-mute">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Validation</div>
        <h1 className="font-sans text-xl font-semibold text-fg">How well did this model do?</h1>
        <ImpactStrip />
        <p className="mt-1 font-sans text-[13px] leading-relaxed">
          Hindcast <span className="text-fg">{r.window}</span>: the model was run every day at 00 UTC with a 48 h horizon; k was fitted on the first {r.fitDays} days and every number below is from the following {r.testDays} days, out of sample. {r.stations} stations ({r.stationsDelhi} within 40 km of Delhi). Fires: {r.fires}. Winds: {r.windLevel}.
        </p>

        <table className="mt-4 w-full">
          <thead><tr className="text-left"><th></th><th className="text-right">R²</th><th className="text-right">MAE µg/m³</th><th className="text-right">bias</th><th className="text-right">corr</th><th className="text-right">n</th></tr></thead>
          <tbody>
            <Row label="model: k·raw + CAMS" m={t.model} />
            <Row label="CAMS background only" m={t.camsOnly} />
            <Row label="lead 1–24 h" m={r.metrics.byLead.lead01_24.model} />
            <Row label="lead 25–48 h" m={r.metrics.byLead.lead25_48.model} />
          </tbody>
        </table>
        <div className="mt-2">increment skill, corr(raw, obs − CAMS): <span className="text-fg">{fmtMetric(t.incrementCorr ?? null)}</span> · k {fmtK(r.k)}{r.kAnomaly !== undefined ? ` · anomaly-fit k ${fmtK(r.kAnomaly)}` : ''}</div>
        <div className="mt-1">Very Poor+ called 24 h ahead: {hr.hits} hits, {hr.misses} misses, {hr.falseAlarms} false alarms, {hr.correctNegatives} correct negatives{hr.informative === false ? <span className="text-fire"> · every test day was Very Poor+, so this rate carries no skill information</span> : ` · POD ${fmtMetric(hr.pod)} · FAR ${fmtMetric(hr.far)}`}</div>
        <div className="mt-1">peak timing error: {r.metrics.peakTiming.meanAbsHours ?? '—'} h mean over {r.metrics.peakTiming.events} events</div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded border border-line bg-panel p-3">
            <div className="mb-1 text-fg">one it got right</div><div className="font-sans text-[13px] leading-relaxed">{r.narrative.right}</div>
          </div>
          <div className="rounded border border-line bg-panel p-3">
            <div className="mb-1 text-fg">one it got wrong</div><div className="font-sans text-[13px] leading-relaxed">{r.narrative.wrong}</div>
          </div>
        </div>

        <div className="mt-5 rounded border border-line bg-panel p-3">
          <div className="mb-1 text-fg">predicted vs observed PM2.5, µg/m³ (test days)</div>
          <div className="h-72">
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

        {r.episodes.map((e) => (
          <div key={e.id} className="mt-4 rounded border border-line bg-panel p-3">
            <div className="mb-1 text-fg">{e.name} · lead 1–24 h, stitched</div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={e.t.map((t, i) => ({ t: t.slice(5, 13).replace('T', ' '), obs: e.obs[i], pred: e.pred[i], bg: e.bg[i] }))} margin={{ top: 4, right: 8, bottom: 0, left: -14 }}>
                  <XAxis dataKey="t" tick={{ fill: '#8b95a3', fontSize: 9 }} interval={47} />
                  <YAxis tick={{ fill: '#8b95a3', fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: '#14181d', border: '1px solid #262c34', fontSize: 11 }} />
                  <Line dataKey="obs" name="observed" stroke="#e8ebef" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                  <Line dataKey="pred" name="model" stroke="#d75b4a" dot={false} isAnimationActive={false} />
                  <Line dataKey="bg" name="CAMS" stroke="#8b95a3" dot={false} strokeDasharray="3 3" isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}

        <table className="mt-5 w-full">
          <thead><tr className="text-left"><th>station</th><th className="text-right">km to Delhi</th><th className="text-right">R²</th><th className="text-right">MAE</th><th className="text-right">bias</th><th className="text-right">CAMS-only MAE</th></tr></thead>
          <tbody>{r.perStation.map((s) => (
            <tr key={s.id} className="border-t border-line"><td className="py-1 text-fg">{s.name}</td><td className="text-right">{s.distanceToDelhiKm}</td><td className="text-right">{fmtMetric(s.r2)}</td><td className="text-right">{fmtMetric(s.mae, 0)}</td><td className="text-right">{fmtMetric(s.bias, 0)}</td><td className="text-right">{fmtMetric(s.camsOnlyMae, 0)}</td></tr>
          ))}</tbody>
        </table>
        <p className="mt-4 font-sans text-[12px] leading-relaxed">{r.disclaimer}</p>
        <Footer label="hindcast" runId={r.experimentId} calibration={{ k: r.k, r2: r.r2, mae: r.mae, window: r.window, stations: r.stations }} />
      </div>
    </div>
  )
}
