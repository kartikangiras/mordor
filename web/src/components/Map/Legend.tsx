// Every number carries its units (DESIGN.md §9.6, §13.4). A key renders only for the layers that
// are on, in toggle order; run metadata lives in the header's "about this run" popover. On the
// free map the panel has a second tab, "What to do": the public guidelines (PIVOT_PLAN.md §5).
import { useState } from 'react'
import { useStore } from '@/lib/store'
import { BURN_CATS, PM25_RAMP, TIERS } from '@/lib/aqi'
import { AwsLogo, NasaLogo } from '@/components/Landing/brandLogos'
import GuidelinesPanel from '@/components/Public/GuidelinesPanel'

export default function Legend({ defaultOpen, inline = false }: { defaultOpen?: boolean; inline?: boolean } = {}) {
  const m = useStore((s) => s.manifest)
  const chapter = useStore((s) => s.chapter)
  const layers = useStore((s) => s.layers)
  const cvd = useStore((s) => s.cvd)
  const toggleCvd = useStore((s) => s.toggleCvd)
  const [open, setOpen] = useState(() => inline || (defaultOpen ?? (typeof window === 'undefined' || window.innerWidth >= 640)))
  const [tab, setTab] = useState<'key' | 'todo'>('key')
  if (!m) return null
  const story = chapter !== null
  const relative = m.overlay.mode === 'relative'
  const anyKey = Object.values(layers).some(Boolean)
  if (!open) return (
    <button type="button" onClick={() => setOpen(true)} className="glass glass-tight absolute bottom-24 left-4 h-9 px-3 font-mono text-[11px] text-mute hover:text-fg max-sm:bottom-40 max-sm:left-2">legend</button>
  )
  return (
    <div className={inline ? 'text-[12px] leading-snug text-mute' : `glass absolute bottom-24 left-4 p-4 text-[12px] leading-snug text-mute ${story ? 'w-64' : 'w-72'}`}>
      {!inline && <div className="mb-3 flex items-start justify-between gap-2">
        {story ? <div className="text-[13px] font-semibold text-fg">Key</div> : (
          <div className="flex gap-1" role="tablist" aria-label="Panel">
            {(['key', 'todo'] as const).map((t) => (
              <button key={t} type="button" role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`h-8 rounded-lg px-2.5 text-[12px] font-medium ${tab === t ? 'bg-white/10 text-fg' : 'text-mute hover:text-fg'}`}>{t === 'key' ? 'Legend' : 'What to do'}</button>
            ))}
          </div>
        )}
        <button type="button" onClick={() => setOpen(false)} className="h-7 w-7 rounded-md text-mute hover:bg-white/5 hover:text-fg" aria-label="hide legend">–</button>
      </div>}
      {tab === 'todo' && !story && !inline ? <GuidelinesPanel compact /> : (
        <>
          {layers.plume && (
            <div className="mb-3">
              <div className="text-[12px] font-semibold text-fg">Smoke added by the fires</div>
              <div className="mb-1.5 font-mono text-[10px] uppercase tracking-wider">PM2.5 · µg/m³ · at the slider hour</div>
              {relative ? (
                <>
                  <div className="h-2.5 w-full rounded-full" style={{ background: `linear-gradient(90deg, transparent, ${m.overlay.low ?? '#F7E07A'}, ${m.overlay.high ?? '#7C2B3F'})` }} />
                  <div className="mt-1 flex justify-between font-mono text-[10px]"><span>thin</span><span>dense</span></div>
                  <div className="mt-1 text-[11px]">Relative density · <span className="text-fire">uncalibrated</span>. Becomes µg/m³ once the run is fitted against stations.</div>
                </>
              ) : (
                <>
                  <div className="flex h-2.5 w-full overflow-hidden rounded-full">{PM25_RAMP.map((s) => <span key={s.from} className="flex-1" style={{ background: s.colour }} />)}</div>
                  <div className="mt-1 flex font-mono text-[10px] text-fg">{PM25_RAMP.map((s, i) => <span key={s.from} className="flex-1">+{s.from}{i === PM25_RAMP.length - 1 ? ' and more' : ''}</span>)}</div>
                  <div className="mt-0.5 text-[10px]">on top of the background already in the air</div>
                </>
              )}
            </div>
          )}
          {layers.fires && (
            <div className="mb-2 flex items-center gap-2">
              <span className="inline-block h-3 w-3 shrink-0 rounded-full border border-[#7C2B3F]" style={{ background: '#FFB347' }} />
              <span>fire seen by VIIRS in the last 24 h · size = how hard it burns · <span className="text-fg">{m.fires.count}</span> detections</span>
            </div>
          )}
          {layers.wind && <div className="mb-2">wind at 925 hPa, the level the smoke travels in · arrows point downwind</div>}
          {layers.stations && (
            <div className="mb-2 space-y-1">
              <div className="flex items-center gap-2"><span className="inline-block h-3.5 w-3.5 shrink-0 rounded-full border-2 border-mute" /><span>reference monitor · CPCB / DPCC / IMD</span></div>
              <div className="flex items-center gap-2"><span className="ml-1 inline-block h-2 w-2 shrink-0 rounded-full border border-mute" /><span>low-cost sensor · AirGradient / Hawanama</span></div>
              <div className="text-[10.5px]">Fill = measured PM2.5 on the ramp. Hollow = older than 3 h: the official feed reaches OpenAQ days late, so most monitors read stale while the sensors are current.</div>
            </div>
          )}
          {layers.zones && <div className="mb-2">zones: circle = city, colour = its tier at the slider hour, label = total µg/m³</div>}
          {layers.burnrisk && <div className="mb-2 flex flex-wrap gap-x-2">burn risk, next 48 h: {BURN_CATS.map((c) => <span key={c.label} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c.colour }} />{c.label}</span>)}</div>}
          {layers.ndvi && <div className="mb-2">crop cover {m.ndvi?.prevDate ? `${m.ndvi.prevDate} → ` : ''}{m.ndvi?.date ?? ''} · green = standing crop, pale = harvested or bare</div>}
          {layers.actors && <div className="mb-2">people: ◆ residents' association · ▲ agriculture office · ✚ hospital · colour = today's tier or burn risk · a ringed, named school dot holds a card · click for the card and its decisions</div>}
          {(layers.schools || layers.actors) && m.schools && (
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              {m.schools.calibrated ? (['T0', 'T1', 'T2', 'T3', 'T4'] as const).map((t) => (
                <span key={t} className="inline-flex h-6 items-center rounded-full px-2 text-[10.5px] font-medium text-ink" style={{ background: TIERS[t].colour }}>{TIERS[t].label}</span>
              )) : <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full bg-[#6b7480]" />No advice yet — the forecast is not calibrated for this run.</span>}
              {layers.schools && <span className="font-mono text-[10px]">· {m.schools.named} schools</span>}
            </div>
          )}
          {!anyKey && <div className="mb-2">No layers on.</div>}
          <button type="button" onClick={toggleCvd} aria-pressed={cvd} className="hairline mt-1 flex min-h-8 w-full items-center justify-between gap-2 rounded-lg px-2.5 text-left text-[11px] text-mute hover:bg-white/5">
            <span>{cvd ? 'Colour-blind ramp' : 'CPCB ramp'} · tap to switch</span>
            <span className="flex shrink-0 gap-0.5" aria-hidden>{PM25_RAMP.map((s) => <span key={s.from} className="inline-block h-3 w-2.5 first:rounded-l-sm last:rounded-r-sm" style={{ background: s.colour }} />)}</span>
          </button>
          <div className="mt-1 text-[10px]">Points, zones and tier bands use this ramp; the smoke image keeps the statutory CPCB colours.</div>
          <div className="mt-3 flex items-center gap-3 border-t border-white/8 pt-2 font-mono text-[10px] text-fg/70"><span className="flex items-center gap-1.5"><NasaLogo className="h-3 w-auto" />FIRMS</span><span className="flex items-center gap-1.5">built on <AwsLogo className="h-3.5 w-auto" /></span></div>
        </>
      )}
    </div>
  )
}
