// /school/:id — public, read-only view of one school's 48 h exposure (DESIGN.md §9.1).
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { getPublicCard } from '@/lib/api'
import type { PublicCard } from '@/lib/protocol'
import { TIERS, type TierId } from '@/lib/aqi'
import { bilinear, cellIndex, domainOf } from '@/lib/grid'
import ExposureChart, { type SeriesPoint } from '@/components/Detail/ExposureChart'
import WindowStrip from '@/components/Protocol/WindowStrip'
import Footer from '@/components/Footer'

const IST_HOUR = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: 'numeric', hour12: false })

export default function SchoolPublic() {
  const { id = '' } = useParams()
  const { manifest, schools, background, grids, load, ensureGrids } = useStore()
  const [card, setCard] = useState<PublicCard | null>(null)

  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  useEffect(() => { if (manifest) { void ensureGrids(); getPublicCard(manifest, id).then(setCard) } }, [manifest, id, ensureGrids])

  const feature = schools?.features.find((f) => f.properties.id === id) ?? null
  const series = useMemo<SeriesPoint[]>(() => {
    if (!feature || !manifest || !background) return []
    const [lon, lat] = feature.geometry.coordinates
    const cell = cellIndex(domainOf(manifest), lat, lon)
    return manifest.hours.map((t, h) => {
      const bg = background.pm25[h] ? bilinear(background.pm25[h], background.lats, background.lons, lat, lon) : 0
      const fire = manifest.calibration.k !== null && cell !== null && grids[h] ? grids[h].values[cell] : null
      const istHour = Number(IST_HOUR.format(new Date(t))) % 24
      return { t, hour: h, bg: Math.round(bg * 10) / 10, fire, total: fire !== null ? Math.round((bg + fire) * 10) / 10 : null, istHour, inSchool: (istHour >= 8 && istHour < 14) || istHour === 15 }
    })
  }, [feature, manifest, background, grids])

  if (!manifest) return <div className="p-6 font-mono text-xs text-mute">loading run…</div>
  if (!feature) return <div className="p-6 text-fg">Unknown school <code className="font-mono text-mute">{id}</code>. <Link className="underline" to="/map">Back to the map</Link></div>
  const p = feature.properties
  const tier = p.dayTier ? TIERS[p.dayTier as TierId] : null
  const calibrated = manifest.calibration.k !== null
  return (
    <div className="min-h-full bg-ink px-4 py-4 text-fg">
      <div className="mx-auto max-w-2xl">
        <h1 className="text-xl font-semibold">{p.name}</h1>
        {p.name_hi && <div className="text-mute">{p.name_hi}</div>}
        <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-xs text-mute">
          {tier ? <span className="rounded px-2 py-1 font-semibold text-ink" style={{ background: tier.colour }}>{p.dayTier} · {tier.label}</span> : <span className="rounded border border-line px-2 py-1">no tier · uncalibrated</span>}
          {p.dayDate && <span>{p.dayDate} school hours</span>}
          {p.peakAqi !== null && <span>peak AQI {p.peakAqi} at {p.peakHourIst}</span>}
        </div>
        {card && card.windows.length > 0 && (
          <div className="mt-4"><div className="mb-1 font-mono text-[11px] text-mute">{card.headline}</div><WindowStrip windows={card.windows} schoolHours={card.schoolHoursIst as [string, string]} dismissal={card.dismissalIst as [string, string]} /></div>
        )}
        <div className="mt-4 rounded border border-line bg-panel p-3">
          <div className="mb-1 font-mono text-xs text-mute">PM2.5 µg/m³ · next 48 h · {calibrated ? 'CAMS background + our fire increment' : 'background only until k is fitted'}</div>
          {series.length ? <ExposureChart series={series} currentHour={0} calibrated={calibrated} /> : <div className="h-56 animate-pulse rounded bg-ink/60" />}
        </div>
        <Footer runId={manifest.runId} generatedAt={manifest.generatedAt} calibration={manifest.calibration} disclaimer={manifest.disclaimer} />
      </div>
    </div>
  )
}
