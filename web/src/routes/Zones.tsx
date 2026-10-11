// /zones — the cities ranked by what the air does to them (PIVOT_PLAN.md task 45): one row per
// zone at every width, the total as the row's number, the fire part of the bar only when there is
// one, the arrival only when it is within 48 h, and the tracer numbers behind one control. Then
// the five cells most likely to burn next, with tonight's detections inline.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { BURN_CATS, TIERS, type TierId } from '@/lib/aqi'
import type { Zone } from '@/lib/api'
import { istClock, istLabel } from '@/lib/time'
import Footer from '@/components/Footer'
import PageBackdrop from '@/components/PageBackdrop'

const fmtM = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : `${Math.round(n / 1e3)} k`)

function Row({ z, i, mode, max, guideline }: { z: Zone; i: number; mode: 'now' | 'peak'; max: number; guideline: string | null }) {
  const [more, setMore] = useState(false)
  const v = mode === 'now' ? z.now : z.peak
  const total = Math.round(v.pm25Total ?? v.pm25Background)
  const fire = v.pm25Fire !== null && v.pm25Fire >= 0.5 ? Math.round(v.pm25Fire) : 0
  const share = v.pm25Total && v.pm25Fire !== null ? Math.round((v.pm25Fire / v.pm25Total) * 100) : null
  const tier = TIERS[v.tier as TierId] ?? TIERS.T0
  const w = (x: number) => `${Math.max(0, Math.min(100, (x / max) * 100))}%`
  const arrival = z.arrivalHour === null ? null : z.arrivalHour === 0 ? 'smoke already here' : `smoke in ${z.arrivalHour} h`
  return (
    <li className="glass glass-tight px-4 py-3" data-zone={z.id}>
      <div className="grid grid-cols-[28px_1fr_auto] items-start gap-x-3 sm:grid-cols-[28px_minmax(0,1.3fr)_minmax(0,1fr)_auto]">
        <div className="pt-0.5 font-mono text-[12px] text-mute">{i + 1}</div>
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold text-fg">{z.name} <span className="font-normal text-mute">{z.name_hi}</span></div>
          <div className="font-mono text-[10.5px] text-mute">{z.region} · ~{fmtM(z.population)} people</div>
        </div>
        <div className="col-span-3 mt-2 max-sm:order-3 sm:col-span-1 sm:mt-0">
          <div className="flex items-baseline gap-2"><span className="font-mono text-[22px] font-light leading-none text-fg">{total}</span><span className="font-mono text-[10px] tracking-wider text-mute">µg/m³ · AQI {v.aqi}</span></div>
          <div className="mt-1.5 flex h-2 w-full overflow-hidden rounded-sm bg-white/10">
            <div style={{ width: w(v.pm25Background), background: '#8b95a3' }} />
            {fire > 0 && <div style={{ width: w(fire), background: '#d75b4a' }} />}
          </div>
          {fire > 0 && <div className="mt-1 font-mono text-[10px] text-[#ff8a75]">fire +{fire} µg/m³{share !== null ? ` · ${share}% of the total` : ''}</div>}
        </div>
        <div className="flex flex-col items-end gap-1 text-right max-sm:order-2 max-sm:col-start-2 max-sm:mt-1 max-sm:flex-row max-sm:flex-wrap max-sm:items-center max-sm:gap-x-2 max-sm:text-left">
          <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold text-ink" style={{ background: tier.colour }}>{tier.label}</span>
          {arrival && <span className="font-mono text-[10px] text-fire">{arrival}</span>}
          {guideline && <span className="text-[11px] leading-snug text-fg/80 sm:max-w-[160px]">{guideline}</span>}
        </div>
      </div>
      <button type="button" onClick={() => setMore(!more)} className="mt-1.5 font-mono text-[10px] text-mute underline hover:text-fg" aria-expanded={more}>{more ? 'less' : 'more'}</button>
      {more && (
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 font-mono text-[11px]">
          <dt className="text-mute">background</dt><dd className="text-fg/90">{Math.round(v.pm25Background)} µg/m³ (CAMS: traffic, industry, dust)</dd>
          <dt className="text-mute">fire share</dt><dd className="text-fg/90">{share === null ? 'not calibrated' : `${share}%`}</dd>
          <dt className="text-mute">NO2 tracer</dt><dd className="text-fg/90">{v.no2 === null ? '—' : `${Math.round(v.no2)} µg/m³ · ${v.no2Band}`}</dd>
          {z.peak.t && <><dt className="text-mute">peak</dt><dd className="text-fg/90">{istLabel(z.peak.t)} IST · {Math.round(z.peak.pm25Total ?? z.peak.pm25Background)} µg/m³ · {TIERS[z.peak.tier as TierId]?.label ?? z.peak.tier}</dd></>}
          {z.arrivalT && <><dt className="text-mute">smoke arrives</dt><dd className="text-fg/90">{istLabel(z.arrivalT)} IST</dd></>}
        </dl>
      )}
    </li>
  )
}

export default function Zones() {
  const { manifest, zones, burning, guidelines, load } = useStore()
  const [mode, setMode] = useState<'now' | 'peak'>('now')
  const [method, setMethod] = useState(false)
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  if (!manifest) return <div className="p-6 font-mono text-xs text-mute">loading run…</div>
  if (!zones) return <div className="p-6 font-mono text-xs text-mute">This run has no zones file. Re-run the pipeline.</div>
  const order = mode === 'now' ? zones.rankingNow : zones.rankingPeak
  const rows = order.map((id) => zones.zones.find((z) => z.id === id)!).filter(Boolean)
  const max = Math.max(...rows.map((z) => (mode === 'now' ? z.now.pm25Total ?? z.now.pm25Background : z.peak.pm25Total ?? z.peak.pm25Background)), 60)
  const burningNow = new Map(burning?.topBurning.map((a) => [`${a.i}-${a.j}`, a]) ?? [])
  const top = burning?.topRisk.slice(0, 5) ?? []
  return (
    <div className="relative min-h-full text-fg">
      <PageBackdrop image="haze" position="55% 45%" />
      <div className="relative mx-auto max-w-3xl px-4 py-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Zones</div>
        <h1 className="text-2xl font-semibold tracking-tight">Exposure zones</h1>
        <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-mute">{zones.note}</p>
        <div className="mt-4 inline-flex rounded-full border border-white/10 bg-white/5 p-1 font-mono text-[11px]" role="tablist" aria-label="Moment">
          {(['now', 'peak'] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={`h-8 rounded-full px-3 transition ${mode === m ? 'bg-fire text-ink' : 'text-mute hover:text-fg'}`}>{m === 'now' ? `now · ${istClock(zones.hours[0])}` : 'peak in 48 h'}</button>
          ))}
        </div>
        <ol className="mt-3 space-y-2" data-zone-list>
          {rows.map((z, i) => <Row key={z.id} z={z} i={i} mode={mode} max={max} guideline={guidelines?.[(z.worstTier in TIERS ? z.worstTier : 'T0') as TierId]?.title ?? null} />)}
        </ol>
        <div className="mt-2 font-mono text-[10px] text-mute">grey = CAMS background · red = the stubble-fire increment, drawn when it is at least 0.5 µg/m³</div>

        {burning && (
          <section className="mt-8" data-burning>
            <h2 className="text-lg font-semibold tracking-tight text-fg">Where it burns next</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-mute">
              The five cells most likely to burn in the next 48 h, scored 0–100 from recent detections, their trend, last season, the vegetation drop and the rain due. {burning.inputs.fires48} detections in the last 48 h this run.
              {' '}<button type="button" onClick={() => setMethod(!method)} className="font-mono text-[11px] underline hover:text-fg" aria-expanded={method}>{method ? 'less' : 'how the score is built'}</button>
            </p>
            {method && <p className="mt-1 font-mono text-[11px] leading-relaxed text-mute">{burning.method}{burning.ndvi ? ` NDVI change ${burning.ndvi.prevDate} → ${burning.ndvi.date}.` : ''}</p>}
            <ol className="mt-3 space-y-2">
              {top.map((a, i) => {
                const cat = BURN_CATS.find((c) => c.label === a.category) ?? BURN_CATS[0]
                const now = burningNow.get(`${a.i}-${a.j}`)
                return (
                  <li key={`${a.i}-${a.j}`} className="glass glass-tight flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2.5">
                    <div className="flex items-center gap-3"><span className="font-mono text-[12px] text-mute">{i + 1}</span><span className="text-[14px] font-medium text-fg">{a.name}</span></div>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10.5px] text-mute">
                      <span>{now ? `${now.fires24} fire${now.fires24 === 1 ? '' : 's'} in 24 h` : a.fires48 ? `${a.fires48} in 48 h` : 'no detections yet'}</span>
                      <span>NDVI {a.ndviChange === null ? '—' : a.ndviChange.toFixed(2)}</span>
                      <span>rain {a.rain48mm ?? '—'} mm</span>
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: cat.colour }}>{a.score} {a.category}</span>
                    </div>
                  </li>
                )
              })}
            </ol>
            <div className="mt-2 font-mono text-[10.5px] text-mute"><Link to="/map?layers=fires,burnrisk,ndvi" className="underline hover:text-fg">Open the map with the burn-risk and crop-cover layers</Link> to see every cell.</div>
          </section>
        )}
        <Footer runId={manifest.runId} generatedAt={manifest.generatedAt} calibration={manifest.calibration} disclaimer={manifest.disclaimer} />
      </div>
    </div>
  )
}
