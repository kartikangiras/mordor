// /zones — the cities ranked by what the air does to them, with the fire share and the traffic
// tracer side by side; and the active burning areas with their 48 h risk score.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { BURN_CATS, TIERS, type TierId } from '@/lib/aqi'
import { istLabel } from '@/lib/time'
import Footer from '@/components/Footer'

function Bar({ bg, fire, max }: { bg: number; fire: number | null; max: number }) {
  const w = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-sm bg-ink">
      <div style={{ width: w(bg), background: '#8b95a3' }} title={`background ${bg}`} />
      {fire !== null && <div style={{ width: w(fire), background: '#d75b4a' }} title={`fire ${fire}`} />}
    </div>
  )
}

export default function Zones() {
  const { manifest, zones, burning, guidelines, load } = useStore()
  const [mode, setMode] = useState<'now' | 'peak'>('now')
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  if (!manifest) return <div className="p-6 font-mono text-xs text-mute">loading run…</div>
  if (!zones) return <div className="p-6 font-mono text-xs text-mute">This run has no zones file. Re-run the pipeline.</div>
  const order = mode === 'now' ? zones.rankingNow : zones.rankingPeak
  const rows = order.map((id) => zones.zones.find((z) => z.id === id)!).filter(Boolean)
  const max = Math.max(...rows.map((z) => (mode === 'now' ? z.now.pm25Total ?? z.now.pm25Background : z.peak.pm25Total ?? z.peak.pm25Background)), 60)
  return (
    <div className="min-h-full bg-ink px-4 py-4 text-fg">
      <div className="mx-auto max-w-4xl font-mono text-xs text-mute">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Zones</div>
        <h1 className="font-sans text-xl font-semibold text-fg">Exposure zones</h1>
        <p className="mt-1 font-sans text-[13px] leading-relaxed">{zones.note}</p>
        <div className="mt-3 flex gap-1">
          {(['now', 'peak'] as const).map((m) => (
            <button key={m} type="button" onClick={() => setMode(m)} className={`h-9 rounded border border-line px-3 ${mode === m ? 'bg-panel text-fg' : ''}`}>{m === 'now' ? `now · ${istLabel(zones.hours[0])} IST` : 'peak in the next 48 h'}</button>
          ))}
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[860px]">
            <thead><tr className="text-left"><th>#</th><th>zone</th><th className="w-48">background + fire, µg/m³</th><th className="text-right">total</th><th className="text-right">AQI</th><th>tier</th><th className="text-right">fire share</th><th className="text-right">NO2 tracer</th><th className="pr-4 text-right">smoke arrives</th><th className="w-40">what to do</th></tr></thead>
            <tbody>
              {rows.map((z, i) => {
                const v = mode === 'now' ? z.now : z.peak
                const total = v.pm25Total ?? v.pm25Background
                const share = v.pm25Total && v.pm25Fire !== null ? v.pm25Fire / v.pm25Total : null
                const tier = TIERS[v.tier as TierId]
                return (
                  <tr key={z.id} className="border-t border-line">
                    <td className="py-1.5">{i + 1}</td>
                    <td className="text-fg">{z.name} <span className="text-mute">{z.name_hi}</span><div className="text-[10px]">{z.region} · ~{(z.population / 1e6).toFixed(1)} M</div></td>
                    <td><Bar bg={v.pm25Background} fire={v.pm25Fire} max={max} /></td>
                    <td className="text-right text-fg">{Math.round(total)}</td>
                    <td className="text-right">{v.aqi}</td>
                    <td><span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: tier.colour }}>{v.tier} {tier.label}</span></td>
                    <td className="text-right">{share === null ? '—' : `${Math.round(share * 100)}%`}</td>
                    <td className="text-right">{v.no2 === null ? '—' : `${Math.round(v.no2)} · ${v.no2Band}`}</td>
                    <td className="pr-4 text-right">{z.arrivalHour === null ? 'not in 48 h' : z.arrivalHour === 0 ? 'already here' : `+${z.arrivalHour} h`}{mode === 'peak' && z.peak.t ? <div className="text-[10px]">peak {istLabel(z.peak.t)}</div> : null}</td>
                    <td className="font-sans text-[11px] text-fg/80" title={guidelines?.[(z.worstTier in TIERS ? z.worstTier : 'T0') as TierId]?.outdoor}>{guidelines?.[(z.worstTier in TIERS ? z.worstTier : 'T0') as TierId]?.title ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-1 text-[10px]">grey = CAMS background (traffic, industry, dust, everything that is not stubble) · red = our stubble-fire increment · NO2 bands follow the European index (low &lt;40, moderate &lt;90, high &lt;120, very high &lt;230 µg/m³)</div>

        {burning && (
          <>
            <h2 className="mt-8 font-sans text-lg font-semibold text-fg">Active burning areas and 48 h burning risk</h2>
            <p className="mt-1 font-sans text-[13px] leading-relaxed">{burning.method} Inputs this run: {burning.inputs.fires48} detections in 48 h{burning.inputs.climatology ? ', 2024 climatology' : ''}{burning.inputs.ndvi ? `, NDVI change ${burning.ndvi?.prevDate} → ${burning.ndvi?.date}` : ''}{burning.inputs.rain ? ', forecast rain' : ''}.</p>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div className="rounded border border-line bg-panel p-3">
                <div className="mb-1 text-fg">burning now · top 8 cells by detections in 24 h</div>
                {burning.topBurning.map((a, i) => (
                  <div key={`${a.i}-${a.j}`} className="flex items-center justify-between border-t border-line py-1">
                    <span>{i + 1}. {a.name}</span>
                    <span className="text-fg">{a.fires24} fires <span className="text-mute">({a.trend >= 0 ? '+' : ''}{a.trend} vs prev 24 h · {a.frp24} MW)</span></span>
                  </div>
                ))}
              </div>
              <div className="rounded border border-line bg-panel p-3">
                <div className="mb-1 text-fg">highest burning risk, next 48 h</div>
                {burning.topRisk.map((a, i) => {
                  const cat = BURN_CATS.find((c) => c.label === a.category) ?? BURN_CATS[0]
                  return (
                    <div key={`${a.i}-${a.j}`} className="flex items-center justify-between border-t border-line py-1">
                      <span>{i + 1}. {a.name}</span>
                      <span><span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: cat.colour }}>{a.score} {a.category}</span> <span className="text-[10px]">NDVI {a.ndviChange === null ? '—' : a.ndviChange.toFixed(2)} · rain {a.rain48mm ?? '—'} mm</span></span>
                    </div>
                  )
                })}
              </div>
            </div>
            <div className="mt-2 text-[10px]"><Link to="/map?layers=fires,burnrisk,ndvi" className="underline">Open the map with the burn-risk and crop-cover layers</Link> to see every cell; click a cell for its score components.</div>
          </>
        )}
        <Footer runId={manifest.runId} generatedAt={manifest.generatedAt} calibration={manifest.calibration} disclaimer={manifest.disclaimer} />
      </div>
    </div>
  )
}
