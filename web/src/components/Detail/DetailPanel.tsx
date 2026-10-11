// Opens on a school click (DESIGN.md §9.4): name, nearest fire, tier chip, the exposure chart.
import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { TIERS, type TierId } from '@/lib/aqi'
import { bilinear, cellIndex, domainOf, haversineKm } from '@/lib/grid'
import ExposureChart, { type SeriesPoint } from './ExposureChart'

const IST_FMT = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: 'numeric', hour12: false })
const DATE_FMT = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short' })

function hhmm(s: string): number { const [h, m] = s.split(':').map(Number); return h * 60 + m }

export default function DetailPanel({ inline = false }: { inline?: boolean } = {}) {
  const selected = useStore((s) => s.selected)
  const select = useStore((s) => s.select)
  const manifest = useStore((s) => s.manifest)
  const schools = useStore((s) => s.schools)
  const background = useStore((s) => s.background)
  const grids = useStore((s) => s.grids)
  const fires = useStore((s) => s.fires)
  const hour = useStore((s) => s.hour)
  const ensureGrids = useStore((s) => s.ensureGrids)

  useEffect(() => { if (selected) void ensureGrids() }, [selected, ensureGrids])

  const series = useMemo<SeriesPoint[]>(() => {
    if (!selected || !manifest || !background) return []
    const [lon, lat] = selected.feature.geometry.coordinates
    const d = domainOf(manifest)
    const cell = cellIndex(d, lat, lon)
    const k = manifest.calibration.k
    const win = schools ? [hhmm(schools.schoolHoursIst[0]), hhmm(schools.schoolHoursIst[1]), hhmm(schools.dismissalIst[0]), hhmm(schools.dismissalIst[1])] : [480, 840, 900, 960]
    return manifest.hours.map((t, h) => {
      const bg = background.pm25[h] ? bilinear(background.pm25[h], background.lats, background.lons, lat, lon) : 0
      const raw = cell !== null && grids[h] ? grids[h].values[cell] : null
      const fire = k !== null && raw !== null ? raw : null   // grid values are already µg/m³ when calibrated
      const istHour = Number(IST_FMT.format(new Date(t))) % 24
      const m = istHour * 60
      const inSchool = (m >= win[0] && m < win[1]) || (m >= win[2] && m < win[3])
      return { t, hour: h, bg: Math.round(bg * 10) / 10, fire, total: fire !== null ? Math.round((bg + fire) * 10) / 10 : null, istHour, inSchool }
    })
  }, [selected, manifest, background, grids, schools])

  if (!selected || !manifest) return null
  const p = selected.feature.properties
  const [lon, lat] = selected.feature.geometry.coordinates
  const tier = (p.dayTier as TierId | null) ? TIERS[p.dayTier as TierId] : null
  const calibrated = manifest.calibration.k !== null
  const nearest = fires?.features.reduce((best, f) => {
    const [flon, flat] = f.geometry.coordinates
    const km = haversineKm(lat, lon, flat, flon)
    return km < best ? km : best
  }, Infinity)
  const gridsReady = manifest.hours.every((_, h) => grids[h])

  return (
    <aside className={inline ? 'text-[12px] text-mute' : 'glass absolute right-4 top-20 bottom-24 w-[min(420px,calc(100%-2rem))] overflow-y-auto p-5 text-[12px] text-mute'}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[16px] font-semibold leading-tight tracking-tight text-fg">{p.name}</div>
          {p.name_hi && <div className="text-[12px] text-mute">{p.name_hi}</div>}
          <div className="mt-1 font-mono text-[10.5px]">nearest fire {Number.isFinite(nearest) ? `${nearest!.toFixed(0)} km` : '—'}</div>
        </div>
        <button type="button" onClick={() => select(null)} aria-label="Close" className="hairline flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-mute hover:bg-white/5 hover:text-fg">×</button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {tier ? (
          <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold text-ink" style={{ background: tier.colour }}>
            {p.dayTier} · {tier.label}
          </span>
        ) : (
          <span className="hairline rounded-full px-2.5 py-1 text-[11px]">No advice yet — the forecast is not calibrated for this run.</span>
        )}
        {p.dayDate && <span>{DATE_FMT.format(new Date(p.dayDate + 'T12:00:00+05:30'))} · school hours</span>}
        {p.peakAqi !== null && <span>peak AQI {p.peakAqi} at {p.peakHourIst}</span>}
      </div>

      <div className="mt-4 border-t border-white/8 pt-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-[13px] font-medium text-fg">PM2.5, µg/m³ · next 48 h</span>
          <span className="text-[10px]">{calibrated ? 'stacked: background + fire increment' : 'background only until k is fitted'}</span>
        </div>
        {series.length && (calibrated ? gridsReady : true) ? (
          <ExposureChart series={series} currentHour={hour} calibrated={calibrated} />
        ) : (
          <div className="h-56 animate-pulse rounded bg-ink/60" />
        )}
        <div className="mt-1 text-[10px]">shaded = school hours {schools?.schoolHoursIst.join('–')} and dismissal {schools?.dismissalIst.join('–')} IST · dashed = CPCB band edges · orange = slider hour</div>
      </div>

      {p.days?.length > 0 && (
        <div className="mt-3 border-t border-white/8 pt-3">
          {p.days.map((d) => (
            <div key={d.date} className="flex items-center justify-between py-0.5">
              <span>{DATE_FMT.format(new Date(d.date + 'T12:00:00+05:30'))}</span>
              <span className="text-fg">{d.tier ? `${d.tier} ${TIERS[d.tier as TierId].label}` : '—'}{d.peakAqi !== null ? ` · peak ${d.peakAqi} @ ${d.peakHourIst}` : ''}</span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2"><Link className="hairline inline-flex h-9 items-center rounded-lg px-3 text-[12px] font-medium text-fg hover:bg-white/5" to={`/school/${encodeURIComponent(p.id)}`}>Open this school's page →</Link>{(p.demo || p.onboarded) && <Link className="hairline inline-flex h-9 items-center rounded-lg px-3 text-[12px] font-medium text-fg hover:bg-white/5" to={`/records/${encodeURIComponent(p.id)}`}>Decisions →</Link>}</div>
      <div className="mt-3 border-t border-white/8 pt-2 font-mono text-[10px]">background CAMS, ~40 km · smoke increment 5 km{calibrated ? '' : ' · not calibrated this run'}</div>
    </aside>
  )
}
